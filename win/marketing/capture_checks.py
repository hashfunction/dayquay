"""Pinned existing Jotmorrow package/evidence for capture only; no new acceptance."""
# Copyright 2026 Trieflow LLC. MIT.
import hashlib
import json
from pathlib import Path,PurePosixPath
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'msix'))
import msix_qualification as msix
from store_workflow_evidence import validate_workflow

SOURCE='64e8174c5f375fecf45539594b6a6b4beac8e025'
RUN='34681664116'
PACKAGE_NAME='Jotmorrow_1.0.1.0_x64.msix'
FULL_NAME='1659hashfunction.DayQuay_1.0.1.0_x64__r3hxytd7jt6c4'
PACKAGE={'bytes':39743804,'sha256':'47b1b5153eedbbf4709ff8dd143164ff90445009137682722da4951e13b066fe'}
LOCKED_IDENTITY={'packageName':'1659hashfunction.DayQuay','publisher':'CN=B6A2631A-FD32-45CC-AE12-82466975F528',
    'version':'1.0.1.0','architecture':'x64','applicationId':'DayQuay','executable':'Jotmorrow.exe','deviceFamily':'Windows.Desktop',
    'minVersion':'10.0.19041.0','maxVersionTested':'10.0.26100.0','capability':'runFullTrust'}


def require(value,message):
    if not value:raise ValueError(message)


def digest(path):
    with msix._regular_stream(Path(path)) as stream:
        h=hashlib.sha256();size=0
        for chunk in iter(lambda:stream.read(1048576),b''):h.update(chunk);size+=len(chunk)
    return {'bytes':size,'sha256':h.hexdigest()}


def read_json(path):
    with msix._regular_stream(Path(path)) as stream:data=stream.read(16*1024*1024+1)
    require(len(data)<=16*1024*1024,'Oversized capture evidence')
    return json.loads(data.decode('utf-8-sig'))


def relative_path(name):
    require(isinstance(name,str) and name and '\\' not in name and ':' not in name and not name.startswith('/')
            and all(part not in ('','.','..') for part in name.split('/')) and str(PurePosixPath(name))==name,'Unsafe artifact/evidence path')
    return name


def assert_current_capture_binding():
    require(msix.STORE_IDENTITY==LOCKED_IDENTITY,'Current product identity differs from pinned existing package')


def validate_receipts(ready,installed,run):
    require(run.get('id')==int(RUN) and run.get('head_sha')==SOURCE and type(run.get('run_attempt')) is int and run['run_attempt']==1
            and run.get('conclusion')=='success' and run.get('repository',{}).get('full_name')=='hashfunction/dayquay'
            and run.get('path')=='.github/workflows/build-windows.yml','Pinned successful qualification run differs')
    require(ready.get('unsigned_store_package_ready') is True and ready.get('identity')==LOCKED_IDENTITY
            and ready.get('unsigned_package')==dict(PACKAGE,name=PACKAGE_NAME)
            and ready.get('reviewed_public_source')==SOURCE,'Pinned Store readiness receipt differs')
    for receipt in (ready,installed):
        require(receipt.get('source_commit')==SOURCE and receipt.get('workflow_run_id')==RUN
                and receipt.get('workflow_run_attempt')=='1','Qualified source/run differs')
    require(installed.get('identity_mode')=='store' and installed.get('package_full_name')==FULL_NAME
            and installed.get('unsigned_package_sha256')==PACKAGE['sha256'],'Qualified installation identity differs')
    for key in ('installation_qualification_passed','journal_backup_restore_workflow_tested','workflow_profile_removed','uninstall_verified','clean_close_verified'):
        require(installed.get(key) is True,'Original installed workflow did not pass: '+key)
    for key in ('cleanup_errors','evidence_errors','residual_package_full_names'):
        require(installed.get(key)==[],'Original qualification has unresolved state: '+key)
    require(installed.get('primary_error') is None and installed.get('certificate_private_key_exported') is False,
            'Original qualification failed or exported private signing inputs')
    require(isinstance(ready.get('evidence'),dict) and ready['evidence'],'Original evidence binding is absent')


def verify_evidence(ready,metadata,source):
    for name,expected in ready['evidence'].items():
        relative_path(name)
        path=Path(metadata)/name.removeprefix('build-evidence/') if name.startswith('build-evidence/') else Path(source)/name
        require(digest(path)==expected,'Original qualification evidence changed: '+name)


def assert_qualified_checkout(source):
    import subprocess
    require(subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==SOURCE,'Qualified source checkout differs')
    require(not subprocess.check_output(['git','-C',str(source),'status','--porcelain=v1','--untracked-files=all'],text=True).strip(),
            'Qualified source checkout contains modified inputs')


def verify_inputs(package,ready_path,metadata,source,run):
    assert_current_capture_binding()
    require(digest(package)==PACKAGE,'Exact qualified unsigned package bytes differ')
    ready=read_json(ready_path);installed=read_json(Path(metadata)/'msix-store-install/installation-qualification.json')
    validate_receipts(ready,installed,run)
    verify_evidence(ready,metadata,source)
    record=read_json(Path(metadata)/'msix-store-package-record.json')
    require(record['sourceCommit']==SOURCE and record['identityMode']=='store' and record['identity']==LOCKED_IDENTITY,'Original Store package record differs')
    require(msix.verify_msix(package,record['payload'],'store')==record['containerVerification'],'Original unsigned container differs from verified payload')
    workflow=read_json(Path(metadata)/'msix-store-install/installed-consumer-workflow.json')
    validate_workflow(workflow,installed,record['windowTitleContract']['expectedTitle'],digest(Path(source)/'win/msix/installed_workflow_qualification.py')['sha256'])
    return record


if __name__=='__main__':
    import argparse,subprocess
    parser=argparse.ArgumentParser();parser.add_argument('--inputs',type=Path,required=True);parser.add_argument('--qualified-source',type=Path,required=True)
    args=parser.parse_args()
    require(subprocess.check_output(['git','-C',str(args.qualified_source),'rev-parse','HEAD'],text=True).strip()==SOURCE,'Qualified checkout differs')
    verify_inputs(args.inputs/'store'/PACKAGE_NAME,args.inputs/'store/release-ready.json',args.inputs/'metadata',args.qualified_source,read_json(args.inputs/'qualified-run.json'))
    print('Verified exact existing Jotmorrow Store package and original successful installed workflow; capture only.')
