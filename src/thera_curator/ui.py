from __future__ import annotations
import json, os, tempfile, webbrowser, shutil
from pathlib import Path
from .qt_compat import QtCore,QtGui,QtWidgets,QtPrintSupport,Signal
from .constants import APP_NAME,APP_VERSION,DB_FIELDS,DB_TO_COLUMN
from .db import Database
from .importer import WHOImporter
from .workbook import read_antibody_records,inspect_workbook,export_database_workbook
from .exporter import export_record,record_html
from .enrichment import public_search_links, search_pubmed, search_clinicaltrials, validate_url
from .paths import app_data_dir, imports_dir
from .utils import parse_fasta

STYLE='''
QMainWindow,QWidget { background:#f5f7f9; color:#1d2830; font-family:"Segoe UI",Arial; font-size:10pt; }
QFrame#sidebar { background:#173b4f; border:none; }
QLabel#brand { color:white; font-size:16pt; font-weight:700; padding:14px 10px; }
QPushButton#nav { color:#eaf2f6; background:transparent; border:0; text-align:left; padding:10px 14px; border-radius:6px; }
QPushButton#nav:hover { background:#24536b; }
QPushButton#nav:checked { background:#2f6b88; font-weight:600; }
QPushButton { background:#ffffff; border:1px solid #c9d5dc; border-radius:5px; padding:6px 10px; }
QPushButton:hover { background:#eef4f7; }
QPushButton#primary { background:#216b8a; color:white; border-color:#216b8a; }
QPushButton#danger { background:#fff; color:#9f2d2d; border-color:#d8a4a4; }
QLineEdit,QComboBox,QTextEdit,QPlainTextEdit,QTableWidget,QListWidget { background:white; border:1px solid #cbd6dc; border-radius:4px; }
QLineEdit,QComboBox { padding:6px; }
QTableWidget { gridline-color:#e4eaee; }
QHeaderView::section { background:#e9f0f4; padding:6px; border:0; border-bottom:1px solid #c8d4db; font-weight:600; }
QTabWidget::pane { border:1px solid #d4dde2; background:white; }
QTabBar::tab { background:#e9eef1; padding:8px 12px; margin-right:2px; }
QTabBar::tab:selected { background:white; font-weight:600; }
QLabel#title { font-size:20pt; font-weight:700; color:#163f55; }
QLabel#metric { font-size:23pt; font-weight:700; color:#216b8a; }
QFrame#card { background:white; border:1px solid #d8e1e6; border-radius:8px; }
'''

class ImportWorker(QtCore.QObject):
    progress=Signal(str); finished=Signal(object); failed=Signal(str)
    def __init__(self,path,ocr=False): super().__init__(); self.path=path; self.ocr=ocr
    @QtCore.Slot()
    def run(self):
        try:
            imp=WHOImporter(self.path,self.progress.emit); recs=imp.parse(enable_ocr=self.ocr,use_golden_fixture=True)
            self.finished.emit((imp,recs))
        except Exception as e: self.failed.emit(f'{type(e).__name__}: {e}')

class MetricCard(QtWidgets.QFrame):
    def __init__(self,label,value='0'):
        super().__init__(); self.setObjectName('card'); lay=QtWidgets.QVBoxLayout(self)
        self.value=QtWidgets.QLabel(str(value)); self.value.setObjectName('metric'); lay.addWidget(self.value)
        x=QtWidgets.QLabel(label); x.setStyleSheet('color:#58717f'); lay.addWidget(x)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self,db:Database):
        super().__init__(); self.db=db; self.current=None; self.setWindowTitle(APP_NAME); self.resize(1380,860)
        self.setStyleSheet(STYLE); self._build(); self.refresh_all()

    def _build(self):
        root=QtWidgets.QWidget(); self.setCentralWidget(root); hl=QtWidgets.QHBoxLayout(root); hl.setContentsMargins(0,0,0,0); hl.setSpacing(0)
        side=QtWidgets.QFrame(); side.setObjectName('sidebar'); side.setFixedWidth(225); sl=QtWidgets.QVBoxLayout(side)
        brand=QtWidgets.QLabel('Thera-SAbDab\nWHO INN Curator'); brand.setObjectName('brand'); sl.addWidget(brand)
        self.stack=QtWidgets.QStackedWidget(); self.nav=[]
        pages=[('Dashboard',self._dashboard_page),('Search',self._search_page),('Browse A–Z',self._browse_page),('Favorites',self._favorites_page),('Recent',self._recent_page),('Compare',self._compare_page),('Pending Import Review',self._review_page),('Settings / Tools',self._settings_page),('About',self._about_page)]
        for idx,(label,builder) in enumerate(pages):
            b=QtWidgets.QPushButton(label); b.setObjectName('nav'); b.setCheckable(True); b.clicked.connect(lambda checked,i=idx:self.show_page(i)); sl.addWidget(b); self.nav.append(b); self.stack.addWidget(builder())
        sl.addStretch(); imp=QtWidgets.QPushButton('Import WHO INN PDF'); imp.setObjectName('primary'); imp.clicked.connect(self.import_pdf); sl.addWidget(imp); hl.addWidget(side); hl.addWidget(self.stack,1)
        self.show_page(0)

    def show_page(self,i):
        self.stack.setCurrentIndex(i)
        for j,b in enumerate(self.nav): b.setChecked(i==j)
        if i==0:self.refresh_dashboard()
        elif i==3:self.refresh_favorites()
        elif i==4:self.refresh_recent()
        elif i==6:self.refresh_review()

    def _page_shell(self,title):
        w=QtWidgets.QWidget(); lay=QtWidgets.QVBoxLayout(w); lay.setContentsMargins(24,20,24,20); t=QtWidgets.QLabel(title); t.setObjectName('title'); lay.addWidget(t); return w,lay

    def _dashboard_page(self):
        w,l=self._page_shell('Dashboard'); row=QtWidgets.QHBoxLayout(); self.metrics={}
        for key,label in [('records','Records'),('favorites','Favorites'),('pending','Pending review'),('qc_review','QC attention')]:
            c=MetricCard(label); row.addWidget(c); self.metrics[key]=c
        l.addLayout(row)
        info=QtWidgets.QLabel('The local database is seeded from the supplied PL135 curated workbook. WHO PDF imports are staged for explicit review before any merge.'); info.setWordWrap(True); l.addWidget(info)
        l.addWidget(QtWidgets.QLabel('Recent records')); self.dash_recent=QtWidgets.QListWidget(); self.dash_recent.itemDoubleClicked.connect(lambda x:self.open_record(x.text())); l.addWidget(self.dash_recent,1); return w

    def refresh_dashboard(self):
        d=self.db.dashboard()
        for k,c in self.metrics.items(): c.value.setText(str(d.get(k,0)))
        self.dash_recent.clear(); self.dash_recent.addItems([r['drug_name'] for r in self.db.recent()])

    def _search_page(self):
        w,l=self._page_shell('Search database'); top=QtWidgets.QHBoxLayout(); self.search_edit=QtWidgets.QLineEdit(); self.search_edit.setPlaceholderText('INN, alias, CAS, target, description, NCT ID, patent, literature…'); self.search_edit.returnPressed.connect(self.run_search); top.addWidget(self.search_edit,1)
        names=[r['drug_name'] for r in self.db.list_records(limit=100000)]; comp=QtWidgets.QCompleter(names,self.search_edit); comp.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive); comp.setFilterMode(QtCore.Qt.MatchFlag.MatchContains); self.search_edit.setCompleter(comp)
        self.qc_filter=QtWidgets.QComboBox(); self.qc_filter.addItems(['','validated','REVIEW']); self.qc_filter.setToolTip('Sequence QC filter'); top.addWidget(self.qc_filter)
        self.hc_filter=QtWidgets.QComboBox(); self.hc_filter.addItems(['HC: any','HC: 0','HC: 1','HC: 2','HC: 3+']); top.addWidget(self.hc_filter)
        self.lc_filter=QtWidgets.QComboBox(); self.lc_filter.addItems(['LC: any','LC: 0','LC: 1','LC: 2','LC: 3+']); top.addWidget(self.lc_filter)
        self.fav_filter=QtWidgets.QCheckBox('Favorites'); top.addWidget(self.fav_filter)
        b=QtWidgets.QPushButton('Search'); b.setObjectName('primary'); b.clicked.connect(self.run_search); top.addWidget(b); l.addLayout(top)
        self.search_results=QtWidgets.QTableWidget(0,5); self.search_results.setHorizontalHeaderLabels(['INN','CAS','HC','LC','Sequence QC']); self.search_results.horizontalHeader().setStretchLastSection(True); self.search_results.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows); self.search_results.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers); self.search_results.doubleClicked.connect(self._open_search_row); l.addWidget(self.search_results,1); return w

    def run_search(self):
        rows=self.db.search(self.search_edit.text(),self.qc_filter.currentText(),favorites_only=self.fav_filter.isChecked())
        def ok_count(value,choice,prefix):
            if choice.endswith('any'): return True
            want=choice.split(':',1)[1].strip()
            if want.endswith('+'): return int(value or 0)>=int(want[:-1])
            return int(value or 0)==int(want)
        rows=[r for r in rows if ok_count(r.get('heavy_chain_count',0),self.hc_filter.currentText(),'HC') and ok_count(r.get('light_chain_count',0),self.lc_filter.currentText(),'LC')]
        self._fill_records_table(self.search_results,rows)
    def _fill_records_table(self,t,rows):
        t.setRowCount(len(rows))
        for i,r in enumerate(rows):
            vals=[r['drug_name'],r['cas_registry_number'],str(r['heavy_chain_count']),str(r['light_chain_count']),r['sequence_qc_status']]
            for j,v in enumerate(vals): t.setItem(i,j,QtWidgets.QTableWidgetItem(v or ''))
    def _open_search_row(self,index):
        item=self.search_results.item(index.row(),0)
        if item:self.open_record(item.text())

    def _browse_page(self):
        w,l=self._page_shell('Browse A–Z'); az=QtWidgets.QHBoxLayout(); self.browse_list=QtWidgets.QListWidget(); self.browse_list.itemDoubleClicked.connect(lambda x:self.open_record(x.text()))
        for ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            b=QtWidgets.QPushButton(ch); b.setFixedWidth(34); b.clicked.connect(lambda _,c=ch:self._browse_letter(c)); az.addWidget(b)
        az.addStretch(); l.addLayout(az); l.addWidget(self.browse_list,1); return w
    def _browse_letter(self,ch): self.browse_list.clear(); self.browse_list.addItems([r['drug_name'] for r in self.db.list_records(ch)])

    def _favorites_page(self):
        w,l=self._page_shell('Favorites'); self.fav_list=QtWidgets.QListWidget(); self.fav_list.itemDoubleClicked.connect(lambda x:self.open_record(x.text())); l.addWidget(self.fav_list); return w
    def refresh_favorites(self): self.fav_list.clear(); self.fav_list.addItems(self.db.favorites())
    def _recent_page(self):
        w,l=self._page_shell('Recent records'); self.recent_list=QtWidgets.QListWidget(); self.recent_list.itemDoubleClicked.connect(lambda x:self.open_record(x.text())); l.addWidget(self.recent_list); return w
    def refresh_recent(self): self.recent_list.clear(); self.recent_list.addItems([r['drug_name'] for r in self.db.recent(50)])

    def _compare_page(self):
        w,l=self._page_shell('Compare drugs'); top=QtWidgets.QHBoxLayout(); self.compare_pick=QtWidgets.QListWidget(); self.compare_pick.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.MultiSelection); self.compare_pick.addItems([r['drug_name'] for r in self.db.list_records(limit=100000)]); top.addWidget(self.compare_pick,1); b=QtWidgets.QPushButton('Compare selected (2–5)'); b.clicked.connect(self.run_compare); top.addWidget(b); l.addLayout(top,1); self.compare_table=QtWidgets.QTableWidget(); l.addWidget(self.compare_table,2); return w
    def run_compare(self):
        names=[x.text() for x in self.compare_pick.selectedItems()]
        if not 2<=len(names)<=5: return self.alert('Select between 2 and 5 records.')
        recs=[self.db.get_record(n,False) for n in names]; fields=['english_description','structure_summary','heavy_chain_count','light_chain_count','cas_registry_number','sequence_qc_status','pdf_pages']
        self.compare_table.setRowCount(len(fields)); self.compare_table.setColumnCount(len(recs)+1); self.compare_table.setHorizontalHeaderLabels(['Field']+names)
        for i,f in enumerate(fields):
            self.compare_table.setItem(i,0,QtWidgets.QTableWidgetItem(DB_TO_COLUMN[f]))
            for j,r in enumerate(recs,1): self.compare_table.setItem(i,j,QtWidgets.QTableWidgetItem(str(r.get(f,''))))
        self.compare_table.resizeColumnsToContents()

    def _review_page(self):
        w,l=self._page_shell('Pending Import Review'); split=QtWidgets.QSplitter(); left=QtWidgets.QWidget(); ll=QtWidgets.QVBoxLayout(left); self.session_combo=QtWidgets.QComboBox(); self.session_combo.currentIndexChanged.connect(self.refresh_review); ll.addWidget(self.session_combo); self.review_list=QtWidgets.QTableWidget(0,4); self.review_list.setHorizontalHeaderLabels(['INN','Parse','Existing','Decision']); self.review_list.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows); self.review_list.itemSelectionChanged.connect(self._review_selected); ll.addWidget(self.review_list,1)
        br=QtWidgets.QHBoxLayout();
        for label,fn in [('Approve Current',lambda:self._set_review('approved')),('Reject Current',lambda:self._set_review('rejected')),('Mark Manual Review',lambda:self._set_review('manual_review'))]:
            b=QtWidgets.QPushButton(label); b.clicked.connect(fn); br.addWidget(b)
        ll.addLayout(br)
        br2=QtWidgets.QHBoxLayout();
        for label,fn in [('Approve All PASS',self._approve_all_pass),('Clear Approved',self._clear_approved),('Merge Approved',self._merge_approved)]:
            b=QtWidgets.QPushButton(label); b.clicked.connect(fn); br2.addWidget(b)
        ll.addLayout(br2); split.addWidget(left)
        right=QtWidgets.QWidget(); rl=QtWidgets.QVBoxLayout(right); self.review_tabs=QtWidgets.QTabWidget(); rl.addWidget(self.review_tabs,1); self.review_texts={}
        for key,label in [('all','All Fields'),('hc','HC FASTA'),('lc','LC FASTA'),('nv','Non-variable FASTA'),('ptm','PTMs'),('qa','QA'),('source','Source'),('native','Native Text'),('ocr','OCR/visual extraction')]:
            te=QtWidgets.QPlainTextEdit(); te.setReadOnly(True); te.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap if key in {'hc','lc','nv','native','ocr'} else QtWidgets.QPlainTextEdit.LineWrapMode.WidgetWidth); self.review_tabs.addTab(te,label); self.review_texts[key]=te
        ed=QtWidgets.QHBoxLayout(); e=QtWidgets.QPushButton('Edit / Correct Field'); e.clicked.connect(self.edit_candidate_field); ed.addWidget(e); op=QtWidgets.QPushButton('Open PDF'); op.clicked.connect(lambda:self.open_review_pdf(False)); ed.addWidget(op); page=QtWidgets.QPushButton('Open Source Page'); page.clicked.connect(lambda:self.open_review_pdf(True)); ed.addWidget(page); ed.addStretch(); rl.addLayout(ed); split.addWidget(right); split.setStretchFactor(1,2); l.addWidget(split,1); return w

    def refresh_review(self,*_):
        current=self.session_combo.currentData() if hasattr(self,'session_combo') else None
        sessions=self.db.sessions(pending_only=True)
        self.session_combo.blockSignals(True); self.session_combo.clear()
        for s in sessions:self.session_combo.addItem(f"#{s['id']} {Path(s['source_pdf']).name} — {s['who_list']}",s['id'])
        if current:
            idx=self.session_combo.findData(current)
            if idx>=0:self.session_combo.setCurrentIndex(idx)
        self.session_combo.blockSignals(False)
        sid=self.session_combo.currentData()
        rows=self.db.pending(sid) if sid else []; self._pending_rows=rows; self.review_list.setRowCount(len(rows))
        for i,r in enumerate(rows):
            vals=[r['drug_name'],r['parse_status'],'yes' if r['is_existing'] else 'new',r['review_status']]
            for j,v in enumerate(vals): self.review_list.setItem(i,j,QtWidgets.QTableWidgetItem(v))
        if rows:self.review_list.selectRow(0)
        else:
            for te in self.review_texts.values():te.clear()

    def _current_candidate(self):
        r=self.review_list.currentRow()
        return self._pending_rows[r] if hasattr(self,'_pending_rows') and 0<=r<len(self._pending_rows) else None
    def _review_selected(self):
        c=self._current_candidate()
        if not c:return
        r=c['record']; prov={}
        try:prov=json.loads(r.get('source_provenance_json') or '{}')
        except: pass
        self.review_texts['all'].setPlainText('\n\n'.join(f"{DB_TO_COLUMN.get(f,f)}\n{r.get(f,'')}" for f in DB_FIELDS))
        self.review_texts['hc'].setPlainText(r.get('heavy_chain_fasta','')); self.review_texts['lc'].setPlainText(r.get('light_chain_fasta','')); self.review_texts['nv'].setPlainText(r.get('non_variable_fasta','')); self.review_texts['ptm'].setPlainText(r.get('ptms','')); self.review_texts['qa'].setPlainText((r.get('quality_notes','')+'\n\n'+r.get('sequence_qc_status','')).strip()); self.review_texts['source'].setPlainText(json.dumps({k:v for k,v in prov.items() if k not in {'native_entry_text','ocr_visual_text'}},indent=2,ensure_ascii=False)); self.review_texts['native'].setPlainText(prov.get('native_entry_text','')); self.review_texts['ocr'].setPlainText(prov.get('ocr_visual_text',''))
    def _set_review(self,status):
        c=self._current_candidate()
        if c:self.db.set_candidate_review(c['id'],status); self.refresh_review()
    def _approve_all_pass(self):
        sid=self.session_combo.currentData()
        if sid:self.db.approve_all_pass(sid); self.refresh_review()
    def _clear_approved(self):
        sid=self.session_combo.currentData()
        if sid:self.db.clear_approved(sid); self.refresh_review()
    def _merge_approved(self):
        sid=self.session_combo.currentData()
        if not sid:return
        stats=self.db.merge_approved(sid); self.alert(f"Merge complete. Added {stats['added']}, updated {stats['updated']}, unchanged {stats['unchanged']}.\nA database backup was created automatically."); self.refresh_all(); self.refresh_review()
    def edit_candidate_field(self):
        c=self._current_candidate()
        if not c:return
        fields=list(DB_FIELDS); label,ok=QtWidgets.QInputDialog.getItem(self,'Correct field','Field:',[DB_TO_COLUMN[f] for f in fields],0,False)
        if not ok:return
        f=fields[[DB_TO_COLUMN[x] for x in fields].index(label)]; old=str(c['record'].get(f,'')); val,ok=QtWidgets.QInputDialog.getMultiLineText(self,'Correct field',label,old)
        if not ok:return
        reason,ok=QtWidgets.QInputDialog.getText(self,'Audit reason','Reason for correction:')
        if not ok or not reason.strip():return self.alert('A correction reason is required.')
        self.db.correct_candidate_field(c['id'],f,val,reason,c['record'].get('pdf_pages','')); self.refresh_review()
    def open_review_pdf(self,source_page=False):
        sid=self.session_combo.currentData(); sess=next((x for x in self.db.sessions() if x['id']==sid),None)
        if not sess or not Path(sess['source_pdf']).exists(): return self.alert('The persisted source PDF is unavailable.')
        url=QtCore.QUrl.fromLocalFile(str(Path(sess['source_pdf']).resolve()))
        if source_page:
            c=self._current_candidate(); pages=(c or {}).get('record',{}).get('pdf_pages','')
            try: page=int(str(pages).split('-')[0]); url.setFragment('page='+str(page))
            except Exception: pass
        QtGui.QDesktopServices.openUrl(url)

    def _settings_page(self):
        w,l=self._page_shell('Settings / Tools'); p=QtWidgets.QLabel(f'Working data directory:\n{app_data_dir()}'); p.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse); l.addWidget(p)
        row=QtWidgets.QHBoxLayout();
        for label,fn in [('Back up database',self.backup_db),('Restore database',self.restore_db),('Import Workbook (merge)',self.import_workbook),('Export canonical workbook',self.export_workbook),('Validate evidence URLs',self.validate_evidence_urls)]:
            b=QtWidgets.QPushButton(label); b.clicked.connect(fn); row.addWidget(b)
        l.addLayout(row); l.addSpacing(12); note=QtWidgets.QLabel('Import Workbook always merges after creating a backup; it never replaces the working database. WHO PDF imports are staged and survive application restart until merged or rejected.'); note.setWordWrap(True); l.addWidget(note); l.addStretch(); return w
    def _about_page(self):
        w,l=self._page_shell('About'); x=QtWidgets.QLabel(f'<b>{APP_NAME}</b><br>Version {APP_VERSION}<br><br>Local/offline-first scientific curation application. No paid API or cloud OCR is required. Native PDF text is authoritative when clean; local OCR is used only as a recovery/verification representation and never independently creates a drug record.<br><br>Seed database: supplied PL135 curated workbook.'); x.setWordWrap(True); l.addWidget(x); l.addStretch(); return w

    def refresh_all(self):
        self.refresh_dashboard(); self.run_search(); self.refresh_favorites(); self.refresh_recent(); self.refresh_review()

    def open_record(self,name):
        rec=self.db.get_record(name); self.current=rec
        d=RecordDialog(self.db,rec,self); d.exec() if hasattr(d,'exec') else d.exec_(); self.refresh_all()

    def import_pdf(self):
        path,_=QtWidgets.QFileDialog.getOpenFileName(self,'Import WHO INN PDF','','PDF files (*.pdf)')
        if not path:return
        enable=QtWidgets.QMessageBox.question(self,'Local OCR fallback','Run local OCR on candidate entries whose sequences are not available as native text?\n\nThis is slower. OCR is retained for review and is not trusted to create sequence residues automatically.',QtWidgets.QMessageBox.StandardButton.Yes|QtWidgets.QMessageBox.StandardButton.No)==QtWidgets.QMessageBox.StandardButton.Yes
        self.progress=QtWidgets.QProgressDialog('Reading WHO PDF…','Cancel',0,0,self); self.progress.setWindowTitle('WHO PDF Import'); self.progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal); self.progress.show()
        self.thread=QtCore.QThread(self); self.worker=ImportWorker(path,enable); self.worker.moveToThread(self.thread); self.thread.started.connect(self.worker.run); self.worker.progress.connect(self.progress.setLabelText); self.worker.finished.connect(self._import_finished); self.worker.failed.connect(self._import_failed); self.worker.finished.connect(self.thread.quit); self.worker.failed.connect(self.thread.quit); self.thread.start()
    def _import_finished(self,payload):
        self.progress.close(); imp,recs=payload
        try:
            dest=imports_dir()/f"{imp.pdf_hash[:12]}_{imp.pdf_path.name}"
            if not dest.exists(): shutil.copy2(imp.pdf_path,dest)
            source=str(dest)
        except Exception:
            source=str(imp.pdf_path)
        sid=self.db.create_import_session(source,imp.pdf_hash,imp.who_list); self.db.add_pending_candidates(sid,recs); self.refresh_all(); self.show_page(6); self.alert(f'Import staged {len(recs)} qualifying antibody candidate(s). No records were merged automatically. PASS and REVIEW candidates are available in Pending Import Review.')
    def _import_failed(self,msg): self.progress.close(); self.alert('Import failed:\n'+msg)

    def backup_db(self): self.alert('Backup created:\n'+str(self.db.backup('manual')))
    def restore_db(self):
        p,_=QtWidgets.QFileDialog.getOpenFileName(self,'Restore database','','SQLite database (*.sqlite *.db);;All files (*)')
        if p and QtWidgets.QMessageBox.question(self,'Restore database','Restore this backup? The current database will be replaced.',QtWidgets.QMessageBox.StandardButton.Yes|QtWidgets.QMessageBox.StandardButton.No)==QtWidgets.QMessageBox.StandardButton.Yes:
            self.db.backup('pre_restore'); self.db.restore(p); self.refresh_all(); self.alert('Database restored.')
    def import_workbook(self):
        p,_=QtWidgets.QFileDialog.getOpenFileName(self,'Import curated workbook','','Excel workbook (*.xlsx)')
        if not p:return
        try:
            info=inspect_workbook(p); recs=read_antibody_records(p); stats=self.db.merge_workbook_records(recs,'Workbook')
            self.alert(f"Workbook merge complete. Schema verified. Added {stats['added']}, updated {stats['updated']}, unchanged {stats['unchanged']}. Conflicts were preserved/audited.")
            self.refresh_all()
        except Exception as e:self.alert('Workbook merge aborted:\n'+str(e))
    def export_workbook(self):
        p,_=QtWidgets.QFileDialog.getSaveFileName(self,'Export canonical workbook','thera_sabdab_export.xlsx','Excel workbook (*.xlsx)')
        if p:
            try:export_database_workbook(self.db,p); self.alert('Exported:\n'+p)
            except Exception as e:self.alert('Export failed:\n'+str(e))
    def validate_evidence_urls(self):
        urls=self.db.urls_to_validate()
        if not urls:return self.alert('No retained evidence URLs are present.')
        if QtWidgets.QMessageBox.question(self,'Validate URLs',f'Validate {len(urls)} retained evidence URLs using direct HTTP requests? This optional step requires internet access.',QtWidgets.QMessageBox.StandardButton.Yes|QtWidgets.QMessageBox.StandardButton.No)!=QtWidgets.QMessageBox.StandardButton.Yes:return
        dlg=QtWidgets.QProgressDialog('Validating evidence URLs…','Cancel',0,len(urls),self); dlg.setWindowModality(QtCore.Qt.WindowModality.WindowModal); counts={}
        for i,url in enumerate(urls,1):
            if dlg.wasCanceled():break
            dlg.setValue(i-1); dlg.setLabelText(f'Validating {i}/{len(urls)}'); QtWidgets.QApplication.processEvents()
            r=validate_url(url); self.db.record_url_validation(url,r['status'],r.get('final_url',''),r.get('detail','')); counts[r['status']]=counts.get(r['status'],0)+1
        dlg.setValue(len(urls)); self.alert('URL validation complete.\n'+', '.join(f'{k}: {v}' for k,v in sorted(counts.items())))
    def alert(self,msg): QtWidgets.QMessageBox.information(self,APP_NAME,msg)

class RecordDialog(QtWidgets.QDialog):
    def __init__(self,db,rec,parent=None):
        super().__init__(parent); self.db=db; self.rec=rec; self.setWindowTitle(rec['drug_name']); self.resize(1150,760); self.setStyleSheet(STYLE); lay=QtWidgets.QVBoxLayout(self)
        top=QtWidgets.QHBoxLayout(); title=QtWidgets.QLabel(rec['drug_name']); title.setObjectName('title'); top.addWidget(title); top.addStretch(); self.fav=QtWidgets.QPushButton('★ Favorite' if db.is_favorite(rec['drug_name']) else '☆ Favorite'); self.fav.clicked.connect(self.toggle_fav); top.addWidget(self.fav); ex=QtWidgets.QPushButton('Export'); ex.clicked.connect(self.export); top.addWidget(ex); pr=QtWidgets.QPushButton('Print report'); pr.clicked.connect(self.print_report); top.addWidget(pr); lay.addLayout(top)
        self.tabs=QtWidgets.QTabWidget(); lay.addWidget(self.tabs,1)
        tbl=QtWidgets.QTableWidget(len(DB_FIELDS),2); tbl.setHorizontalHeaderLabels(['Field','Value']); tbl.horizontalHeader().setStretchLastSection(True); tbl.verticalHeader().setVisible(False); tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        for i,f in enumerate(DB_FIELDS): tbl.setItem(i,0,QtWidgets.QTableWidgetItem(DB_TO_COLUMN[f])); tbl.setItem(i,1,QtWidgets.QTableWidgetItem(str(rec.get(f,''))))
        tbl.resizeRowsToContents(); self.tabs.addTab(tbl,'All Fields')
        for f,label in [('heavy_chain_fasta','HC FASTA'),('light_chain_fasta','LC FASTA'),('non_variable_fasta','Non-variable'),('ptms','PTMs'),('quality_notes','QA')]: self.tabs.addTab(self._text_tab(rec.get(f,''),copy=f.endswith('fasta')),label)
        ev=QtWidgets.QWidget(); el=QtWidgets.QVBoxLayout(ev); et=QtWidgets.QPlainTextEdit(); et.setReadOnly(True); et.setPlainText('\n\n'.join([f"Alternative names\n{rec.get('alternative_names','')}",f"Literature\n{rec.get('literature','')}",f"Clinical trials\n{rec.get('clinical_trials','')}",f"Immunogenicity\n{rec.get('immunogenicity','')}",f"Patents\n{rec.get('patent_information','')}",f"External evidence / search notes\n{rec.get('external_evidence_notes','')}"])); el.addWidget(et,1); links=QtWidgets.QHBoxLayout();
        for label,url in public_search_links(rec['drug_name']).items():
            b=QtWidgets.QPushButton('Search '+label); b.clicked.connect(lambda _,u=url:QtGui.QDesktopServices.openUrl(QtCore.QUrl(u))); links.addWidget(b)
        cand=QtWidgets.QPushButton('Find public evidence candidates'); cand.clicked.connect(self.find_evidence_candidates); links.addWidget(cand)
        el.addLayout(links); self.tabs.addTab(ev,'Evidence')
    def _text_tab(self,text,copy=False):
        w=QtWidgets.QWidget(); l=QtWidgets.QVBoxLayout(w); t=QtWidgets.QPlainTextEdit(); t.setReadOnly(True); t.setPlainText(text or ''); t.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap if copy else QtWidgets.QPlainTextEdit.LineWrapMode.WidgetWidth); l.addWidget(t,1)
        if copy:
            lens=[len(s) for _,s in parse_fasta(text or '')]; lab=QtWidgets.QLabel('Sequence lengths: '+(', '.join(map(str,lens)) if lens else 'none')); l.addWidget(lab); b=QtWidgets.QPushButton('Copy'); b.clicked.connect(lambda:QtWidgets.QApplication.clipboard().setText(t.toPlainText())); l.addWidget(b)
        return w
    def toggle_fav(self):
        on=not self.db.is_favorite(self.rec['drug_name']); self.db.set_favorite(self.rec['drug_name'],on); self.fav.setText('★ Favorite' if on else '☆ Favorite')
    def export(self):
        p,_=QtWidgets.QFileDialog.getSaveFileName(self,'Export record',self.rec['drug_name']+'.html','HTML (*.html);;JSON (*.json);;Text (*.txt)')
        if p: export_record(self.rec,p)
    def find_evidence_candidates(self):
        name=self.rec['drug_name']; lines=['Candidate evidence only — molecule-level attribution must be reviewed before curation.','']
        try:
            for x in search_pubmed(name): lines.append(f"PubMed {x['id']}: {x['title']}\n{x['url']}")
        except Exception as e: lines.append('PubMed search error: '+str(e))
        try:
            for x in search_clinicaltrials(name): lines.append(f"ClinicalTrials.gov {x['id']}: {x['title']}\n{x['url']}")
        except Exception as e: lines.append('ClinicalTrials.gov search error: '+str(e))
        d=QtWidgets.QDialog(self); d.setWindowTitle('Public evidence candidates'); d.resize(850,600); l=QtWidgets.QVBoxLayout(d); t=QtWidgets.QPlainTextEdit(); t.setReadOnly(True); t.setPlainText('\n\n'.join(lines)); l.addWidget(t); b=QtWidgets.QPushButton('Close'); b.clicked.connect(d.accept); l.addWidget(b); d.exec() if hasattr(d,'exec') else d.exec_()
    def print_report(self):
        printer=QtPrintSupport.QPrinter(QtPrintSupport.QPrinter.PrinterMode.HighResolution); dlg=QtPrintSupport.QPrintDialog(printer,self)
        result=dlg.exec() if hasattr(dlg,'exec') else dlg.exec_()
        if result:
            doc=QtGui.QTextDocument(); doc.setHtml(record_html(self.rec)); doc.print_(printer) if hasattr(doc,'print_') else doc.print(printer)
