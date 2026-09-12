"""Type an original journal and capture real backup/restore UI in the fixed binary."""
# Copyright 2026 Trieflow LLC. MIT.
import argparse
import datetime
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

SENTINEL='A slower day, with room to notice things.'
MARKER='Keep a little space for the unexpected.'


def entry(day):
    return f'''{day.strftime('%A')} notes | {day.strftime('%d %B %Y')}

{SENTINEL}

A walk by the river
The morning light made the water look silver. I left my phone in my
bag, took the longer path home, and stopped for coffee on the corner.
A small reminder that a good day does not need a crowded schedule.

An idea worth keeping
Make a Sunday ritual of choosing one thing to learn, one person to
catch up with, and one small task that will make the week easier.

Grateful for
- A conversation that lasted longer than planned.
- Fresh bread, an open window, and time to read a few chapters.
- The feeling of finishing one thing before starting another.

For next week
Book the library workshop. Print a favorite photo for the desk.
{MARKER}

#weekend #ideas #gratitude
'''


def run_capture(ui,original,journal,archive,parent,restore_name,day):
    initial_title=ui.current_title
    text=entry(day)
    ui.replace_editor_text(text);ui.save()
    saved=original._eventually(lambda:original.capture_journal(journal,SENTINEL,(MARKER,'#weekend #ideas #gratitude')),'saved original marketing entry')
    ui.show_top();ui.capture('01-journal-entry')
    ui.create_backup(archive)
    backup=original._eventually(lambda:original.verify_backup(archive,saved),'actual portable backup')
    title=original.restored_window_title(initial_title,restore_name)
    ui.restore_backup(archive,parent,restore_name,title)
    restored=original._eventually(lambda:original.verify_restored(parent/restore_name,SENTINEL,MARKER,saved),'actual restored journal')
    protected=original.verify_protected_journal(journal,SENTINEL,MARKER,saved)
    backup_after=original.verify_protected_backup(archive,saved,backup)
    ui.show_top();ui.capture('03-restored-journal')
    return dict(schema_version=1,purpose='real marketing screenshots only',consumer_acceptance=False,
                original_fixture_copyright='Copyright 2026 Trieflow LLC; fictional journal, no customer data.',
                sample_date=day.isoformat(),typed_text=text,saved=saved,backup=backup,restored=restored,
                original_after_restore=protected,backup_after_restore=backup_after,restored_title=title)


def journal_diagnostics(original,journal):
    """Read bounded fictional capture files only; this never grants acceptance."""
    files=original._regular_tree(journal)
    if len(files)!=1:raise ValueError('Expected one exclusive fictional month file')
    name,record=next(iter(files.items()))
    if '/' in name or not original.MONTH_NAME.fullmatch(name) or record['bytes']>65536:
        raise ValueError('Fictional journal diagnostic exceeds its month/size scope')
    text=record['content'].decode('utf-8')
    return dict(filename=name,bytes=record['bytes'],sha256=record['sha256'],
        required_text_counts={s:text.count(s) for s in (SENTINEL,MARKER,'#weekend #ideas #gratitude')},
        fictional_saved_text=text[:4096],text_truncated=len(text)>4096)


def ui_class(original,args,captures,frame):
    class UI(original._WindowsInput):
        VK=dict(original._WindowsInput.VK,HOME=0x24)
        def show_top(self):self._main();self.chord('CTRL','HOME')
        def capture(self,name,target=None,title=None):
            self._assert_process_live()
            target=self.main_hwnd if target is None else target
            title=self.current_title if title is None else title
            self._foreground(target,title)
            frame([args.powershell,'-NoProfile','-File',str(Path(__file__).with_name('capture_frame.ps1')),
                '-ProcessId',str(self.process_id),'-MainWindowHandle',str(self.main_hwnd),'-TargetWindowHandle',str(target),
                '-MainTitle',self.current_title,'-TargetTitle',title,'-Record',str(args.record),'-OutputStem',str(args.output/name)])
            captures.append(name)
        def _wait_window(self,title,present=True,timeout=12.0):
            hwnd=super()._wait_window(title,present,timeout)
            if present and title=='Restore portable backup':
                if '02-restore-preview' in captures:raise ValueError('Unexpected repeated restore confirmation')
                self.capture('02-restore-preview',hwnd,title)
            return hwnd
    return UI


def main():
    parser=argparse.ArgumentParser()
    for name in ('qualified-source','profile-root','archive','output','record'):
        parser.add_argument('--'+name,type=Path,required=True)
    for name in ('process-id','main-window-handle'):parser.add_argument('--'+name,type=int,required=True)
    parser.add_argument('--initial-title',required=True);parser.add_argument('--powershell',required=True)
    args=parser.parse_args()
    path=args.qualified_source/'win/msix/installed_workflow_qualification.py'
    spec=importlib.util.spec_from_file_location('qualified_workflow',path)
    original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
    captures=[]
    UI=ui_class(original,args,captures,lambda command:subprocess.run(command,check=True,timeout=30))
    ui=UI(args.process_id,args.main_window_handle,args.initial_title)
    try:
        result=run_capture(ui,original,args.profile_root/'data',args.archive,args.profile_root,'RestoredJournal',datetime.date.today())
        if captures!=['01-journal-entry','02-restore-preview','03-restored-journal']:raise ValueError('Missing real native capture stage')
        result.update(process_id=args.process_id,main_window_handle=args.main_window_handle,captures=captures)
        original._write_json_exclusive(args.output/'journal-capture.json',result)
    except Exception as error:
        failure=dict(captured=False,consumer_acceptance=False,error=str(error),native=ui.failure_diagnostics())
        try:failure['fictional_journal']=journal_diagnostics(original,args.profile_root/'data')
        except Exception as diagnostic:failure['journal_diagnostic_error']=str(diagnostic)
        try:ui.capture('failure-window')
        except Exception as diagnostic:failure['screenshot_diagnostic_error']=str(diagnostic)
        original._write_json_exclusive(args.output/'journal-capture-failure.json',failure)
        raise
    finally:ui.close()


if __name__=='__main__':main()
