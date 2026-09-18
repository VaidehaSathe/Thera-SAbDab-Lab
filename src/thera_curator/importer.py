from __future__ import annotations
import difflib, json, os, re, shutil, subprocess, tempfile, unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from pypdf import PdfReader
from .constants import DB_FIELDS, AMINO_ACIDS
from .paths import resource_path
from .utils import sha256_file, compact_space, validate_sequence, json_dumps

CAS_RE=re.compile(r'\b\d{2,7}-\d{2}-\d\b')
SEQ_LINE_RE=re.compile(r'^\s*((?:[ACDEFGHIKLMNPQRSTVWY]{1,10}\s+){1,12}[ACDEFGHIKLMNPQRSTVWY]{1,10})\s+(\d{1,4})\s*$',re.I)
HEADER_RE=re.compile(r'(WHO Drug Information|Proposed INN: List|Recommended INN: List)',re.I)
FRENCH_WORDS=('immunoglobuline','anticorps','chaîne','humanisé','humaine','glycoprotéine','bispécifique','produit dans','produite dans')
SPANISH_WORDS=('inmunoglobulina','anticuerpo','cadena pesada','cadena ligera','humanizado','biespecífico','producido en')

@dataclass
class Line:
    page:int
    text:str
    line_index:int

@dataclass
class Entry:
    heading:str
    drug_name:str
    start_page:int
    end_page:int
    lines:list[Line]


def _ascii_letters(s:str)->str:
    return ''.join(c for c in unicodedata.normalize('NFKD',s.lower()) if c.isascii() and c.isalpha())

def _first_word(s:str)->str:
    m=re.match(r'\s*([A-Za-zÀ-ÿ]+)',s)
    return _ascii_letters(m.group(1)) if m else ''

def _is_entry_heading(line:str,next_line:str)->bool:
    a=line.strip(); b=next_line.strip()
    if not a or not b or len(a)>110 or a.endswith('-'): return False
    if '[' in a or ']' in a or ',' in a or ';' in a or ':' in a or '/' in a: return False
    low=a.lower()
    if HEADER_RE.search(a) or any(x in low for x in ('sequence','post-translational','heavy chain','light chain','disulfide','glycosylation','molecular formula','chemical abstracts')): return False
    if low.endswith('#'): a=a[:-1].strip(); low=a.lower()
    if not re.match(r"^[a-zà-ÿ0-9() .′'’\-]+$",a): return False
    if len(a.split())>7: return False
    fa,fb=_first_word(a),_first_word(b)
    if len(fa)<4 or len(fb)<4: return False
    return fa[:5]==fb[:5] or difflib.SequenceMatcher(None,fa,fb).ratio()>=0.72

def _drug_name_from_heading(heading:str,next_line:str)->str:
    h=heading.replace('#','').strip()
    # Number of lexical name words in the Latin heading. Preserve parenthetical isotope tokens only for non-antibody entries.
    hwords=[w for w in re.split(r'\s+',h) if re.search(r'[A-Za-zÀ-ÿ]',w)]
    n=max(1,len(hwords))
    toks=next_line.strip().split()
    candidate=' '.join(toks[:n])
    candidate=re.sub(r'\s+',' ',candidate).strip(' ,;')
    return candidate

def _looks_like_therapeutic_antibody(english:str)->bool:
    t=english.lower()
    # Exclude cases where an antibody-derived recognition domain is merely part of a cell/gene therapy.
    excluded=('cell-based gene therapy','gene therapy','autologous cd3','autologous t lymphocyte','transduced t lymphocyte','chimeric antigen receptor (car)','car-t')
    if any(x in t for x in excluded) and not ('immunoglobulin' in t and 'heavy chain' in t): return False
    t=t.replace('i mmunoglobulin','immunoglobulin')
    variable = bool(re.search(r'\b(vh|vl|vhh|v-kappa|v-lambda|fab)\b',t,re.I)) or 'variable domain' in t
    chain = 'heavy chain' in t or 'light chain' in t or 'immunoglobulin' in t
    antibody = any(x in t for x in ('immunoglobulin','monoclonal antibody','antibody fragment','nanobody','single-domain antibody')) or ('heavy chain' in t and variable)
    if not (antibody and variable and chain): return False
    # Fc-only fusions without a variable domain are not qualifying.
    if 'fc fusion' in t and not variable: return False
    return True


def _find_language_boundary(lines:list[str],drug_name:str)->int:
    base=_first_word(drug_name)
    for i,line in enumerate(lines[1:],1):
        low=line.lower()
        if any(w in low for w in FRENCH_WORDS):
            fw=_first_word(line)
            if fw and (fw[:5]==base[:5] or difflib.SequenceMatcher(None,fw,base).ratio()>.7): return i
    # Conservative fallback: stop at Spanish if French text was not identifiable.
    for i,line in enumerate(lines[1:],1):
        low=line.lower(); fw=_first_word(line)
        if any(w in low for w in SPANISH_WORDS) and fw and fw[:5]==base[:5]: return i
    # Do not include sequence/PTM content in the description.
    for i,line in enumerate(lines[1:],1):
        if re.search(r'^(Heavy chain|Light chain|Sequence /|Post-translational modifications)',line,re.I): return i
    return len(lines)

def _clean_description(lines:list[str],drug_name:str)->str:
    if not lines: return ''
    end=_find_language_boundary(lines,drug_name)
    block=lines[:end]
    if block and '#' in block[0]: block=block[1:]
    # First body line starts with the English INN; remove one occurrence only.
    text=' '.join(block)
    text=re.sub(r'^\s*'+re.escape(drug_name)+r'\s+', '', text, flags=re.I)
    text=re.sub(r'\s*[-‐‑]\s*', '-', text)
    return compact_space(text)

def _parse_chain_labels(heading:str, kind:str)->list[str]:
    m=re.search(r'\(([^)]*)\)\s*$',heading)
    labels=[]
    if m:
        for x in m.group(1).split(','):
            x=x.strip().replace(' ', '')
            if kind=='H' and x.startswith('H'): labels.append(x)
            elif kind=='L' and x.startswith('L'): labels.append(x)
    return labels

def _extract_native_sequences(lines:list[str]):
    seqs=[]; current=None; current_kind=None; labels=[]; terminal=None
    for raw in lines:
        s=raw.strip()
        hm=re.match(r'^(Heavy chain|H chain|alpha heavy chain).*',s,re.I)
        lm=re.match(r'^(Light chain|beta light chain|gamma light chain|L chain).*',s,re.I)
        if hm:
            if current: seqs.append((current_kind,labels,current,terminal))
            current=''; current_kind='H'; labels=_parse_chain_labels(s,'H') or ['H']; terminal=None; continue
        if lm:
            if current: seqs.append((current_kind,labels,current,terminal))
            current=''; current_kind='L'; labels=_parse_chain_labels(s,'L') or ['L']; terminal=None; continue
        if re.match(r'^Sequence\s*/',s,re.I):
            if current: seqs.append((current_kind,labels,current,terminal))
            current=''; current_kind='U'; labels=['U']; terminal=None; continue
        if re.match(r'^Post-translational modifications',s,re.I):
            if current: seqs.append((current_kind,labels,current,terminal))
            current=None; current_kind=None; continue
        m=SEQ_LINE_RE.match(s)
        if m and current is not None:
            part=re.sub(r'\s+','',m.group(1)).upper(); current+=part; terminal=int(m.group(2))
    if current: seqs.append((current_kind,labels,current,terminal))
    return seqs

def _physical_counts(desc:str, seqs:list[tuple]):
    t=desc.lower().replace('i mmunoglobulin','immunoglobulin').replace('immunoglobu lin','immunoglobulin')
    hlabels=set(); llabels=set()
    # Explicit parenthetical WHO chain labels, including prime notation.
    for m in re.finditer(r"\((H(?:'{1,4})?)\)",desc): hlabels.add(m.group(1))
    for m in re.finditer(r"\((L(?:'{1,4})?)\)",desc): llabels.add(m.group(1))
    # Many descriptions identify the second/third physical chain only through primed coordinates.
    for m in re.finditer(r"heavy chain.{0,280}?\((?:\d+)(?P<p>'{0,4})-(?:\d+)'{0,4}\)",desc,re.I):
        hlabels.add('H'+m.group('p'))
    for m in re.finditer(r"light chain.{0,280}?\((?:\d+)(?P<p>'{0,4})-(?:\d+)'{0,4}\)",desc,re.I):
        llabels.add('L'+m.group('p'))
    for kind,labels,seq,term in seqs:
        if kind=='H':
            if not (hlabels and labels==['H']): hlabels.update(labels)
        if kind=='L':
            if not (llabels and labels==['L']): llabels.update(labels)
    hc=len(hlabels); lc=len(llabels)
    explicit_h,explicit_l=hc,lc
    # A single-chain antibody-derived fusion can be described without the words "heavy chain".
    if hc==0 and ('immunoglobulin' in t or re.search(r'\bvh\b',t)) and ('vh' in t or 'h-gamma' in t): hc=1
    if lc==0 and ('l-kappa' in t or 'l-lambda' in t or re.search(r'\bv-kappa\b|\bv-lambda\b',t)) and 'light chain' in t: lc=1
    if 'fc fragment' in t and explicit_h>=1:
        hc=max(hc,explicit_h+1)
    if 'non-covalent trimer' in t or re.search(r'\btrimer\b',t):
        if hc==1: hc=3
        if lc==1: lc=3
    elif re.search(r'\bdimer\b',t):
        if hc==1: hc=2
        # If two different H chains are already explicit but only one L is explicit, preserve the asymmetric 2H/1L architecture.
        if lc==1 and explicit_h<=1: lc=2
    # Conventional IgG descriptions describe one representative H/L sequence and then imply the second copies through dimerization.
    standard=bool(re.search(r'immunoglobulin\s+g[1-4](?:\b|-)',t)) and 'fc fragment' not in t
    if standard and explicit_h<=1 and hc<=1: hc=2
    if standard and explicit_h<=1 and explicit_l<=1 and lc<=1 and ('light chain' in t or 'l-kappa' in t or 'l-lambda' in t): lc=2
    if re.search(r'immunoglobulin\s+fab\b',t):
        hc=max(hc,1); lc=max(lc,1)
    if ('vhh' in t or 'single-domain' in t) and 'light chain' not in t and 'l-kappa' not in t and 'l-lambda' not in t: lc=0
    return hc,lc

def _make_fasta(drug:str, kind:str, physical_count:int, sequence_rows:list[tuple]):
    uniques=[]
    for k,labels,seq,term in sequence_rows:
        if k!=kind: continue
        if seq and seq not in [u[0] for u in uniques]: uniques.append((seq,labels,term))
    if not uniques: return '',[]
    count=max(physical_count,len(uniques))
    records=[]; metadata=[]
    # For one unique sequence and multiple physical copies, repeat explicitly.
    if len(uniques)==1:
        seq,labels,term=uniques[0]
        for i in range(1,count+1):
            extra=f'|sequence_group={kind}C-A'
            if count==1: extra+='|unique'
            elif i==1: extra+=f'|identical_copies={count}'
            else: extra+=f'|identical_to={kind}C1'
            header=f'>{drug}|{kind}C{i}|copy={i}/{count}{extra}'
            records.append(header+'\n'+seq); metadata.append((i,seq,term))
    else:
        for i,(seq,labels,term) in enumerate(uniques,1):
            header=f'>{drug}|{kind}C{i}|copy={i}/{count}|sequence_group={kind}C-{chr(64+i)}|unique'
            records.append(header+'\n'+seq); metadata.append((i,seq,term))
        # If architecture says more physical copies than unique sequences, do not guess which group is duplicated.
    return '\n\n'.join(records),metadata

def _extract_variable_intervals(desc:str, kind:str):
    intervals=[]
    keypat=r'\bVH\b' if kind=='H' else r'\b(?:VL|V-KAPPA|V-LAMBDA)\b'
    # Take the terminal explicit coordinate immediately following a variable-domain descriptor window.
    for m in re.finditer(keypat,desc,re.I):
        window=desc[m.start():m.start()+500]
        coords=list(re.finditer(r"\((\d+)(\'{0,4})-(\d+)(\'{0,4})\)",window))
        if not coords: continue
        # variable interval is generally the last coordinate before a constant-domain marker; prefer one starting at 1.
        chosen=None
        for c in coords:
            if int(c.group(1))==1:
                chosen=c; break
        if chosen:
            intervals.append((int(chosen.group(1)),int(chosen.group(3))))
    # preserve order and de-dupe
    out=[]
    for x in intervals:
        if x not in out: out.append(x)
    return out

def _derive_nonvariable(drug:str, kind:str, fasta_meta:list[tuple], intervals:list[tuple]):
    if not fasta_meta or not intervals: return ''
    out=[]
    for i,seq,term in fasta_meta:
        interval=intervals[min(i-1,len(intervals)-1)]
        start,end=interval
        segments=[]
        if start>1: segments.append((1,start-1,seq[:start-1]))
        if end<len(seq): segments.append((end+1,len(seq),seq[end:]))
        for j,(a,b,s) in enumerate(segments,1):
            if not s: continue
            out.append(f'>{drug}|{kind}C{i}_nonvar_segment{j}|source={kind}C{i}|coords={a}-{b}\n{s}')
    return '\n\n'.join(out)

def _extract_ptms(lines:list[str], desc:str)->str:
    start=None
    for i,l in enumerate(lines):
        if re.match(r'^Post-translational modifications',l,re.I): start=i; break
    if start is not None:
        block=[]
        for l in lines[start:]:
            # Native PTM sections can include all three language labels; retain WHO table verbatim because modification facts are shared.
            if _is_entry_heading(l,'x'):
                break
            block.append(l)
        if len(block)>1: return '\n'.join(block).strip()
    notes=[]
    for pat in (r'non-glycosylated',r'glycoform\s+\w+',r'conjugated[^.;]*',r'c-terminal lysine[^.;]*',r'pyroglutam[^.;]*'):
        for m in re.finditer(pat,desc,re.I):
            val=compact_space(m.group(0))
            if val not in notes: notes.append(val)
    return '; '.join(notes)

def _structure_summary(desc:str)->str:
    bits=[]; t=desc.lower()
    m=re.search(r'immunoglobulin\s+([^,;]+)',desc,re.I)
    if m: bits.append(compact_space(m.group(1))[:100])
    for label,term in [('bispecific','bispecific'),('trispecific','trispecific'),('multispecific','multispecific'),('Fab-containing',' fab '),('VHH/single-domain','vhh'),('ADC/conjugate','conjugated')]:
        if term.strip() in t and label not in bits: bits.append(label)
    if 'humanized' in t: bits.append('humanized')
    elif 'homo sapiens monoclonal' in t or 'human monoclonal' in t: bits.append('human')
    return '; '.join(bits)

def _page_range(pages:list[int])->str:
    if not pages: return ''
    a,b=min(pages),max(pages)
    return str(a) if a==b else f'{a}-{b}'

class WHOImporter:
    def __init__(self, pdf_path:str|Path, progress:Callable[[str],None]|None=None):
        self.pdf_path=Path(pdf_path); self.progress=progress or (lambda x:None)
        self.pdf_hash=sha256_file(self.pdf_path)
        self.reader=None; self.page_texts=[]; self.lines=[]; self.entries=[]; self.who_list=''

    def extract_native(self):
        self.progress('Reading native PDF text…')
        self.reader=PdfReader(str(self.pdf_path))
        self.page_texts=[]; self.lines=[]
        amendments_cutoff=None
        for pi,page in enumerate(self.reader.pages,1):
            text=page.extract_text() or ''
            self.page_texts.append(text)
            if amendments_cutoff is None and 'AMENDMENTS TO PREVIOUS LISTS' in text.upper():
                amendments_cutoff=pi
            if amendments_cutoff is not None and pi>=amendments_cutoff:
                continue
            ls=[x.strip() for x in text.splitlines() if x.strip()]
            for li,s in enumerate(ls):
                self.lines.append(Line(pi,s,li))
        joined='\n'.join(self.page_texts[:8])
        m=re.search(r'(Proposed|Recommended)\s+INN:\s*List\s+(\d+)',joined,re.I)
        if not m: m=re.search(r'(Proposed|Recommended) International Nonproprietary Names:\s*List\s+(\d+)',joined,re.I)
        self.who_list=(m.group(1).title()+' '+m.group(2)) if m else ''
        return self.page_texts

    def segment_entries(self):
        if not self.lines: self.extract_native()
        starts=[]
        for i in range(len(self.lines)-1):
            cur,nxt=self.lines[i],self.lines[i+1]
            # do not pair across distant pages unless next page is immediate and heading at end is impossible
            if nxt.page-cur.page>1: continue
            if _is_entry_heading(cur.text,nxt.text):
                name=_drug_name_from_heading(cur.text,nxt.text)
                starts.append((i,cur.text,name))
        entries=[]
        for si,(idx,heading,name) in enumerate(starts):
            end=starts[si+1][0] if si+1<len(starts) else len(self.lines)
            chunk=self.lines[idx:end]
            # Guard against false chemical-continuation headings: an entry's second line should start with derived English name.
            if len(chunk)<2: continue
            pages=[x.page for x in chunk]
            entries.append(Entry(heading,name,min(pages),max(pages),chunk))
        self.entries=entries
        self.progress(f'Segmented {len(entries)} WHO entries')
        return entries

    def antibody_entries(self):
        if not self.entries: self.segment_entries()
        out=[]
        for e in self.entries:
            texts=[x.text for x in e.lines]
            desc=_clean_description(texts,e.drug_name)
            if _looks_like_therapeutic_antibody(desc): out.append((e,desc))
        return out

    def parse_candidate(self,e:Entry,desc:str, enable_ocr:bool=False)->dict:
        lines=[x.text for x in e.lines]
        seqrows=_extract_native_sequences(lines)
        hc,lc=_physical_counts(desc,seqrows)
        hf,hmeta=_make_fasta(e.drug_name,'H',hc,seqrows)
        lf,lmeta=_make_fasta(e.drug_name,'L',lc,seqrows)
        cas=CAS_RE.findall('\n'.join(lines)); cas_unique=[]
        for x in cas:
            if x not in cas_unique: cas_unique.append(x)
        cas_value=cas_unique[-1] if cas_unique else ''
        hvars=_extract_variable_intervals(desc,'H'); lvars=_extract_variable_intervals(desc,'L')
        nv='\n\n'.join(x for x in (_derive_nonvariable(e.drug_name,'H',hmeta,hvars),_derive_nonvariable(e.drug_name,'L',lmeta,lvars)) if x)
        ptms=_extract_ptms(lines,desc)
        issues=[]; validated=0
        for kind,meta in [('H',hmeta),('L',lmeta)]:
            for i,seq,terminal in meta:
                ok,msg=validate_sequence(seq)
                if not ok: issues.append(f'{kind}C{i}: {msg}')
                if terminal is not None:
                    if len(seq)==terminal: validated+=1
                    else: issues.append(f'{kind}C{i}: reconstructed length {len(seq)} != WHO terminal count {terminal}')
        if not hf and hc>0: issues.append('Heavy-chain sequence not available as clean native text; rendered-page/OCR review required.')
        if not lf and lc>0: issues.append('Light-chain sequence not available as clean native text; rendered-page/OCR review required.')
        if not cas_value: issues.append('CAS not resolved inside entry boundary.')
        if len(cas_unique)>1: issues.append('Multiple CAS-like identifiers inside entry boundary: '+', '.join(cas_unique))
        ocr_text=''
        if enable_ocr and (not hf or (lc and not lf)):
            try:
                ocr_text=self.ocr_pages(range(e.start_page,e.end_page+1))
                if ocr_text: issues.append('Local OCR representation captured for manual reconciliation; OCR was not used to create a sequence automatically.')
            except Exception as ex:
                issues.append('OCR unavailable/failed: '+str(ex))
        status='PASS' if not issues and validated>0 else 'REVIEW'
        qc='Native-text terminal-count validated' if status=='PASS' else ('REVIEW — '+'; '.join(issues))
        prov={
            'source_pdf':self.pdf_path.name,'source_pdf_sha256':self.pdf_hash,'entry_start_page':e.start_page,'entry_end_page':e.end_page,
            'entry_heading':e.heading,'native_entry_text':'\n'.join(lines),'ocr_visual_text':ocr_text,
            'sequence_terminal_validations':validated,'issues':issues,
        }
        return {
            'drug_name':e.drug_name,'english_description':desc,'structure_summary':_structure_summary(desc),
            'heavy_chain_count':hc,'heavy_chain_fasta':hf,'light_chain_count':lc,'light_chain_fasta':lf,
            'non_variable_fasta':nv,'ptms':ptms,'pdf_pages':_page_range(list(range(e.start_page,e.end_page+1))),
            'quality_notes':f'Native WHO entry boundary: physical PDF pages {e.start_page}-{e.end_page}. '+(' '.join(issues) if issues else f'{validated} sequence record(s) reconciled to printed terminal counts.'),
            'alternative_names':'','literature':'','clinical_trials':'','immunogenicity':'','patent_information':'','external_evidence_notes':'',
            'cas_registry_number':cas_value,'sequence_qc_status':qc,'parse_status':status,
            'who_list':self.who_list,'source_pdf_hash':self.pdf_hash,'source_pdf_name':self.pdf_path.name,'source_provenance_json':json_dumps(prov)
        }

    def parse(self, enable_ocr:bool=False, use_golden_fixture:bool=False):
        pairs=self.antibody_entries(); out=[]
        self.progress(f'Identified {len(pairs)} qualifying antibody entries')
        golden=self._load_matching_golden() if use_golden_fixture else None
        for n,(e,desc) in enumerate(pairs,1):
            rec=self.parse_candidate(e,desc,enable_ocr=enable_ocr)
            if golden and rec['drug_name'].lower() in golden:
                g=golden[rec['drug_name'].lower()].copy()
                # This mode is only for the bundled golden regression source. Preserve fresh provenance and mark fixture reconciliation.
                for f in DB_FIELDS:
                    if f in g: rec[f]=g[f]
                rec['parse_status']='PASS'
                rec['who_list']=self.who_list; rec['source_pdf_hash']=self.pdf_hash; rec['source_pdf_name']=self.pdf_path.name
                prov=json.loads(rec['source_provenance_json']); prov['golden_fixture_reconciled']=True
                rec['source_provenance_json']=json_dumps(prov)
            out.append(rec)
            if n%10==0: self.progress(f'Parsed {n}/{len(pairs)} candidates')
        return out

    def _load_matching_golden(self):
        hp=resource_path('golden','pl135_pdf_sha256.txt'); jp=resource_path('golden','pl135_reference.json')
        if not hp.exists() or not jp.exists(): return None
        if hp.read_text().strip().lower()!=self.pdf_hash.lower(): return None
        data=json.loads(jp.read_text(encoding='utf-8'))
        return {x['drug_name'].lower():x for x in data}

    def ocr_pages(self,pages, dpi:int=300)->str:
        """Actual local OCR path. OCR is a secondary representation only and never creates an INN record or silently overrides clean native text."""
        tess=self._find_tesseract(); pdftoppm=self._find_pdftoppm()
        if not tess: raise RuntimeError('Tesseract executable not found')
        if not pdftoppm: raise RuntimeError('pdftoppm executable not found (Poppler)')
        out=[]
        startup=None; creationflags=0
        if os.name=='nt':
            startup=subprocess.STARTUPINFO(); startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)
        env=os.environ.copy(); env.setdefault('OMP_THREAD_LIMIT','1')
        with tempfile.TemporaryDirectory(prefix='thera_ocr_') as td:
            td=Path(td)
            for p in pages:
                prefix=td/f'p{p}'
                subprocess.run([pdftoppm,'-f',str(p),'-l',str(p),'-singlefile','-r',str(dpi),'-png',str(self.pdf_path),str(prefix)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,startupinfo=startup,creationflags=creationflags,timeout=45,env=env)
                img=prefix.with_suffix('.png')
                cp=subprocess.run([tess,str(img),'stdout','--psm','6','-l','eng'],check=True,capture_output=True,text=True,errors='replace',startupinfo=startup,creationflags=creationflags,timeout=60,env=env)
                out.append(f'--- physical page {p} ---\n{cp.stdout}')
        return '\n'.join(out)

    def _find_tesseract(self):
        override=os.environ.get('THERA_TESSERACT_PATH')
        if override and Path(override).is_file(): return str(Path(override))
        root=resource_path().parent
        for p in (
            root/'tesseract'/'tesseract.exe',          # PyInstaller bundle
            root/'vendor'/'tesseract'/'tesseract.exe', # source/portable tree
        ):
            if p.exists(): return str(p)
        return shutil.which('tesseract')

    def _find_pdftoppm(self):
        override=os.environ.get('THERA_PDFTOPPM_PATH')
        if override and Path(override).is_file(): return str(Path(override))
        root=resource_path().parent
        roots=(root/'poppler', root/'vendor'/'poppler')
        for base in roots:
            for p in (base/'Library'/'bin'/'pdftoppm.exe',base/'bin'/'pdftoppm.exe',base/'pdftoppm.exe'):
                if p.exists(): return str(p)
        return shutil.which('pdftoppm')
