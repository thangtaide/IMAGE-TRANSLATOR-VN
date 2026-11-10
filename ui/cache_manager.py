"""Read-only inventory off the UI thread; narrowly scoped, confirmed cache pruning."""
from pathlib import Path
from contextlib import closing
import os
import sqlite3
import time

from PySide6.QtCore import QThread, Signal, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QDialog, QGridLayout, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QVBoxLayout)

from core.paths import CACHE, ROOT
from core.run_cache import RunRegistry


def open_cache_directory(database, parent=None):
    path=Path(database).absolute().parent
    if not path.is_dir():
        QMessageBox.information(parent,'Thư mục cache chưa tồn tại',str(path)+'\nChưa tạo thư mục mới.');return False
    if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
        QMessageBox.warning(parent,'Không mở được thư mục cache',str(path));return False
    return True


def bounded_size(path, seconds=1.5):
    total=0;count=0;complete=True;start=time.monotonic()
    for folder,dirs,files in os.walk(path,followlinks=False):
        dirs[:]=[d for d in dirs if not (Path(folder)/d).is_symlink() and not
                 (getattr((Path(folder)/d).stat(),'st_file_attributes',0)&1024)]
        for name in files:
            p=Path(folder)/name
            if not p.is_symlink():
                try:total+=p.stat().st_size
                except OSError:pass
            count+=1
            if count>=50000 or time.monotonic()-start>seconds:return total,False
    return total,complete


class CacheTask(QThread):
    result=Signal(dict)
    def __init__(self,registry,action='inventory',run_id=None,kinds=None,parent=None):
        super().__init__(parent);self.registry,self.action,self.run_id,self.kinds=registry,action,run_id,kinds
    def run(self):
        try:
            if self.action=='prune':
                value=self.registry.prune(self.run_id,self.kinds)
            elif self.action=='backup':
                value={'backup':str(self.registry.backup(self.run_id))}
            else:
                db=self.registry.database;jobs=0;kinds={}
                if db.is_file():
                    with closing(sqlite3.connect(db.as_uri()+'?mode=ro',uri=True,timeout=.25)) as connection:
                        jobs=connection.execute('SELECT count(*) FROM jobs').fetchone()[0]
                        kinds=dict(connection.execute('SELECT kind,count(*) FROM cache GROUP BY kind'))
                size,complete=bounded_size(db.parent)
                value={'runs':self.registry.inventory(),'shared_jobs':jobs,'shared_kinds':kinds,
                    'shared_bytes':sum(p.stat().st_size for p in [db,db.with_name(db.name+'-wal'),db.with_name(db.name+'-shm')] if p.is_file()),
                    'bytes':size,'size_complete':complete,
                    'runs_complete':not self.registry.inventory_incomplete,
                    'other_locations':[str(CACHE/'online_comics'),str(CACHE/'agy'),str(ROOT/'output'/'stage3g-*')],
                    'shared_updated':time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(db.stat().st_mtime)) if db.exists() else 'Chưa có'}
            self.result.emit({'ok':True,'action':self.action,'value':value})
        except Exception as exc:
            self.result.emit({'ok':False,'action':self.action,'error':str(exc)})


class CacheManagerDialog(QDialog):
    restoreRequested=Signal(str)
    def __init__(self,registry,current_database,parent=None):
        super().__init__(parent);self.registry=registry;self.current_database=Path(current_database)
        from ui.theme import apply_dark_theme
        apply_dark_theme()
        self.task=None;self.task_pending=False;self.records=[];self.setWindowTitle('Quản lý cache an toàn')
        screen=self.screen().availableGeometry();self.resize(min(880,screen.width()-60),min(620,screen.height()-60))
        layout=QVBoxLayout(self);layout.setSpacing(12)
        self.location=QLabel('Cache đang dùng: '+str(self.current_database.parent)+'\nDB: '+str(self.current_database))
        self.location.setWordWrap(True);self.location.setTextInteractionFlags(Qt.TextSelectableByMouse);layout.addWidget(self.location)
        self.summary=QLabel('Đang thống kê trong nền…');self.summary.setWordWrap(True);layout.addWidget(self.summary)
        self.table=QTableWidget(0,5);self.table.setHorizontalHeaderLabels(['Run / nguồn','Trạng thái','Loại cache','Dung lượng','Cập nhật'])
        self.table.setSelectionBehavior(QTableWidget.SelectRows);self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers);self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2,QHeaderView.Stretch);layout.addWidget(self.table,1)
        self.table.itemSelectionChanged.connect(self.selection_changed)
        note=QLabel('DB chung và dữ liệu Whole/ToonCN: chỉ xem, chưa dọn vì không xác định ownership an toàn. '
            'Checkpoint, output, models, config và đăng nhập luôn được giữ. Chỉ dọn OCR/bản dịch trong run riêng đã hoàn tất.')
        note.setWordWrap(True);layout.addWidget(note)
        choices=QHBoxLayout();self.ocr=QCheckBox('OCR');self.translation=QCheckBox('Bản dịch')
        self.ocr.setChecked(True);self.translation.setChecked(True)
        self.render=QCheckBox('Render / checkpoint (được bảo vệ)');self.render.setEnabled(False)
        for widget in [self.ocr,self.translation,self.render]:choices.addWidget(widget)
        layout.addLayout(choices)
        self.open=QPushButton('Mở thư mục cache');self.refresh=QPushButton('Làm mới')
        self.backup=QPushButton('Sao lưu lượt đã chọn');self.prune=QPushButton('Dọn OCR / bản dịch đã chọn…')
        self.restore=QPushButton('Mở / khôi phục lượt đã chọn');self.close_button=QPushButton('Đóng')
        tools=QGridLayout()
        for i,button in enumerate([self.open,self.refresh,self.backup,self.prune,self.restore,self.close_button]):tools.addWidget(button,i//3,i%3)
        layout.addLayout(tools)
        self.open.clicked.connect(lambda:open_cache_directory(self.current_database,self))
        self.refresh.clicked.connect(self.refresh_inventory);self.backup.clicked.connect(lambda:self.perform('backup'))
        self.prune.clicked.connect(self.confirm_prune);self.restore.clicked.connect(self.restore_run);self.close_button.clicked.connect(self.reject)
        self.selection_changed();self.refresh_inventory()

    def refresh_inventory(self):self.launch('inventory')

    def selected(self):
        row=self.table.currentRow()
        return self.records[row] if 0<=row<len(self.records) else None

    def selection_changed(self):
        record=self.selected();idle=not self.task_pending and not (self.task and self.task.isRunning())
        managed=bool(record and record.get('run_id'))
        self.backup.setEnabled(idle and managed and not record.get('busy',False))
        self.prune.setEnabled(idle and managed and record.get('cleanable',False))
        self.prune.setToolTip('Chỉ dọn cache của run riêng đã hoàn tất. Luôn sao lưu trước bằng SQLite backup và transaction.')
        self.restore.setEnabled(idle and managed and not record.get('busy',False))

    def launch(self,action,run_id=None,kinds=None):
        if self.task_pending or (self.task and self.task.isRunning()):return
        self.task_pending=True
        self.refresh.setEnabled(False);self.task=CacheTask(self.registry,action,run_id,kinds,self)
        self.task.result.connect(self.handle_result);self.task.finished.connect(self.task_finished)
        self.task.start();self.selection_changed()

    def task_finished(self):
        self.task_pending=False
        self.refresh.setEnabled(True);self.selection_changed()

    def handle_result(self,result):
        if not result['ok']:
            self.summary.setText('Không thực hiện: '+result['error']);return
        data=result['value']
        if result['action']!='inventory':
            self.summary.setText('Đã hoàn tất. Backup: '+data['backup']+
                (' • Số mục dọn: '+str(data['deleted_entries']) if 'deleted_entries' in data else ''));return
        self.records=[dict(label='Cache chung — chỉ xem',state='được bảo vệ',kinds=data['shared_kinds'],
            bytes=data['shared_bytes'],updated=data['shared_updated'])]+data['runs']
        self.table.setRowCount(len(self.records))
        for row,record in enumerate(self.records):
            values=[record.get('label',record.get('run_id','')[:12]+' • '+Path(record.get('source','')).name),
                ('đang sử dụng' if record.get('busy') else record.get('state','?')),
                ', '.join(k+': '+str(v) for k,v in record.get('kinds',{}).items()),
                f"{record.get('bytes',0)/1024/1024:.2f} MB",record.get('updated',record.get('created',''))[:19]]
            for col,value in enumerate(values):
                item=QTableWidgetItem(value);item.setToolTip(value);self.table.setItem(row,col,item)
        self.summary.setText(f"Dung lượng {'tối thiểu ' if not data['size_complete'] else ''}{data['bytes']/1024/1024:.2f} MB • "
            f"Job chung: {data['shared_jobs']} • Run riêng: {len(data['runs'])}\n"
            + ('Danh sách run được giới hạn theo thời gian; chưa thống kê toàn bộ.\n' if not data['runs_complete'] else '')+
            'Các vùng được bảo vệ khác: '+', '.join(data['other_locations']))
        self.selection_changed()

    def perform(self,action):
        record=self.selected()
        if record and record.get('run_id'):
            kinds=[]
            if self.ocr.isChecked():kinds.append('ocr')
            if self.translation.isChecked():kinds.append('translation')
            self.launch(action,record['run_id'],kinds)

    def confirm_prune(self):
        record=self.selected()
        if not record or not record.get('cleanable'):return
        kinds=[name for name,box in [('OCR',self.ocr),('bản dịch',self.translation)] if box.isChecked()]
        if not kinds:return
        answer=QMessageBox.question(self,'Xác nhận dọn cache',
            'Dọn '+', '.join(kinds)+' của run '+record['run_id']+'?\n'+record['database']+
            '\nSao lưu DB và journal trước khi dọn. Không xóa checkpoint, output hoặc cache của run khác.',
            QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        if answer==QMessageBox.Yes:self.perform('prune')

    def restore_run(self):
        record=self.selected()
        if record and record.get('run_id') and self.restore.isEnabled():
            self.restoreRequested.emit(record['run_id']);self.accept()

    def reject(self):
        if self.task and self.task.isRunning():
            self.summary.setText('Đang hoàn tất thao tác nền; đóng sau khi thao tác kết thúc.');return
        super().reject()

    def closeEvent(self,event):
        if self.task and self.task.isRunning():event.ignore();self.reject()
        else:super().closeEvent(event)
