"""Prueba local reproducible. No publica código ni usa OCI. Worker = sonda.

python probar_integracion.py --platform linux/amd64 --keep
python probar_integracion.py --platform linux/arm64
python probar_integracion.py --down --platform linux/amd64
"""
import argparse
import copy
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
(ROOT / 'docs').mkdir(exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform', choices=['linux/amd64', 'linux/arm64'], default='linux/amd64')
    parser.add_argument('--keep', action='store_true')
    parser.add_argument('--down', action='store_true')
    args = parser.parse_args()
    arch = args.platform.split('/')[1]
    report_file = ROOT / 'docs' / f'integracion-{arch}.json'
    project = 'communitylab-local-check-' + secrets.token_hex(5)
    port_socket = socket.socket()
    port_socket.bind(('127.0.0.1', 0))
    port = port_socket.getsockname()[1]
    port_socket.close()
    if args.down:
        saved = json.loads(report_file.read_text(encoding='utf-8'))
        project, port = saved['project'], saved['port']
        if not project.startswith('communitylab-local-check-'):
            raise ValueError('Proyecto no reconocido')
    env = dict(os.environ)
    for key in list(env):
        if key.startswith('COMPOSE_'):
            del env[key]
    env.update(POSTGRES_DB='communitylab_local_check', POSTGRES_USER='local_check',
               POSTGRES_PASSWORD=secrets.token_hex(24), DOCKER_PLATFORM=args.platform,
               HTTP_BIND_ADDRESS='127.0.0.1', HTTP_PORT=str(port),
               WEB_IMAGE=f'communitylab-entrega-web:{arch}', API_IMAGE=f'communitylab-entrega-api:{arch}',
               WORKER_IMAGE=f'communitylab-local-worker-probe:{arch}',
               PROXY_IMAGE='nginx:stable-alpine', POSTGRES_IMAGE='postgres:16-alpine')
    # Explicit empty env file avoids loading personal .env files.
    empty_env = ROOT / '.env.integration-empty'
    empty_env.write_text('', encoding='utf-8')
    base = ['docker', 'compose', '--env-file', str(empty_env), '-p', project,
            '-f', 'docker-compose.yml', '-f', 'compose.integracion.yml']
    log_file = ROOT / 'docs' / f'integracion-{arch}.log'
    def cmd(arguments, timeout=1200):
        result = subprocess.run(arguments, cwd=ROOT, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                encoding='utf-8', errors='replace', timeout=timeout)
        # Never run commands that print container environments or private credentials.
        with log_file.open('a', encoding='utf-8') as log:
            log.write('$ ' + ' '.join(arguments) + '\n' + result.stdout + '\n')
        if result.returncode:
            raise RuntimeError(result.stdout[-6000:])
        return result.stdout.strip()
    if args.down:
        try:
            cmd(base + ['down', '--volumes', '--remove-orphans'])
            saved['cleanup'] = 'passed'
            report_file.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding='utf-8')
            print('Proyecto de prueba retirado:', project)
        finally:
            empty_env.unlink(missing_ok=True)
        return
    log_file.write_text('', encoding='utf-8')
    report = {'project': project, 'port': port, 'url': f'http://127.0.0.1:{port}',
              'platform': args.platform, 'started_utc': datetime.now(timezone.utc).isoformat(),
              'scope': 'Frontend y backend mock de Ian; PostgreSQL y Nginx reales; worker sonda. Sin OCI ni IA.',
              'checks': [], 'limitations': [], 'status': 'running'}
    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        report['checks'].append(name)
        print('PASS', name, flush=True)
    def request(path, data=None, method=None, raw=None):
        payload = raw if raw is not None else (json.dumps(data).encode() if data is not None else None)
        req = urllib.request.Request(report['url'] + path, data=payload, method=method,
                                     headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                return response.status, response.read().decode()
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode()
    def wait_http():
        for _ in range(45):
            try:
                if request('/api/v1/procesamientos', data=sample)[0] == 200:
                    return
            except (OSError, TimeoutError):
                pass
            time.sleep(1)
        raise AssertionError('API no recuperó respuesta vía proxy')
    sample = {'origen_comunidad': 'demo_local_ficticia', 'periodo_referencia': '2026-W38',
              'interacciones': [{'id': f'm-0{n}', 'autor': f'persona_demo_{n}',
                  'canal': 'pruebas', 'fecha': '2026-09-23T10:00:00Z',
                  'texto': text} for n, text in enumerate([
                      'Conseguí mi primer empleo.', '¿Cómo configuro reintentos?',
                      'Tengo dudas con los reintentos.', 'Participé en una mentoría.',
                      'Compartimos avances semanales.', 'Tengo un bloqueo con OCI.'], 1)]}
    (ROOT / 'docs' / 'lote-prueba.json').write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding='utf-8')
    try:
        cmd(base + ['config', '--quiet'])
        print('Construyendo aplicaciones para', args.platform, flush=True)
        cmd(base + ['build'], timeout=2400)
        print('Arrancando proyecto aislado', project, flush=True)
        cmd(base + ['up', '-d', '--wait', '--wait-timeout', '240'], timeout=300)
        services = cmd(base + ['ps', '--services']).splitlines()
        check('Cinco servicios iniciados', set(services) == {'web','api','worker','postgres','proxy'})
        report['containers'] = []
        for service in services:
            cid = cmd(base + ['ps', '-q', service])
            state = json.loads(cmd(['docker','inspect','--format','{{json .State}}',cid]))
            check(f'{service}: healthy', state.get('Health', {}).get('Status') == 'healthy')
            actual_arch = cmd(base + ['exec', '-T', service, 'uname', '-m'])
            check(f'{service}: arquitectura {arch}', actual_arch == ('aarch64' if arch == 'arm64' else 'x86_64'))
            ports = json.loads(cmd(['docker','inspect','--format','{{json .HostConfig.PortBindings}}',cid])) or {}
            if service != 'proxy':
                check(f'{service}: sin puertos públicos', not ports)
            else:
                check('Proxy restringido a localhost', all(x['HostIp']=='127.0.0.1' for items in ports.values() for x in items))
            report['containers'].append({'service':service,'id':cid,'architecture':actual_arch,
                'image_id':cmd(['docker','inspect','--format','{{.Image}}',cid])})
        check('Panel Next.js accesible mediante proxy', 'CommunityLab' in request('/')[1])
        check('Proxy saludable', request('/healthz')[0] == 200)
        code, content = request('/api/v1/procesamientos', sample)
        data = json.loads(content)
        check('POST válido responde 200', code == 200)
        direct_script = "fetch('http://127.0.0.1:3000/api/v1/procesamientos',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(" + json.dumps(sample) + ")}).then(async r=>{const d=await r.json();if(r.status!==200||d.activos_distribucion_generados?.length!==3)process.exit(1);console.log('ok')}).catch(()=>process.exit(1))"
        check('Next.js conecta con API sin pasar por Nginx', cmd(base + ['exec','-T','web','node','-e',direct_script]) == 'ok')
        check('Mock devuelve tres formatos', {x['formato'] for x in data['activos_distribucion_generados']} == {'linkedin','faq','newsletter'})
        check('Alerta interna separada', len(data['alertas_internas']) == 1 and data['alertas_internas'][0]['fuente']=='m-06')
        check('OCI declarado simulado', data['almacenamiento_oci']['estado']=='simulado_pendiente_worker')
        check('Resumen corresponde a seis entradas', '6 interacciones' in data['resumen_comunidad'])
        ids = {x['id'] for x in sample['interacciones']}
        check('Fuentes del mock existen en el lote de prueba', all(set(x['fuentes']) <= ids for x in data['activos_distribucion_generados']))
        check('Entrada incompleta rechazada', request('/api/v1/procesamientos', {})[0] == 422)
        check('JSON malformado rechazado', request('/api/v1/procesamientos', raw=b'{broken')[0] == 422)
        invalid = copy.deepcopy(sample); invalid['interacciones'][0].pop('texto')
        check('Mensaje sin texto rechazado', request('/api/v1/procesamientos', invalid)[0] == 422)
        invalid = copy.deepcopy(sample); invalid['interacciones']='not-a-list'
        check('Tipo de interacciones inválido rechazado', request('/api/v1/procesamientos', invalid)[0] == 422)
        check('GET no sustituye POST', request('/api/v1/procesamientos')[0] == 405)
        alternate = copy.deepcopy(sample)
        for message in alternate['interacciones']:
            message['id_mensaje'] = message.pop('id')
        check('Discrepancia id_mensaje reproducida (422)', request('/api/v1/procesamientos', alternate)[0] == 422)
        report['limitations'] += ['Contrato del mock usa id; esquema propuesto por José usa id_mensaje. Se requiere acordar adaptación antes de integrar el dataset.',
            'Mock devuelve contenido fijo y no valida semántica de fechas, vacíos ni existencia de las fuentes para lotes arbitrarios. Solo se prueba el contrato inicial, no IA.',
            'API mock no guarda datos en PostgreSQL. La persistencia siguiente prueba la infraestructura por separado.']
        cmd(base + ['exec','-T','postgres','psql','-U','local_check','-d','communitylab_local_check','-c',
                    'CREATE TABLE local_integration_probe (id integer PRIMARY KEY); INSERT INTO local_integration_probe VALUES (1);'])
        cmd(base + ['restart','postgres'])
        for _ in range(30):
            try:
                count=cmd(base+['exec','-T','postgres','psql','-U','local_check','-d','communitylab_local_check','-tAc','SELECT count(*) FROM local_integration_probe;'])
                break
            except RuntimeError:
                time.sleep(1)
        else:
            raise AssertionError('PostgreSQL no recuperó')
        check('Registro de infraestructura persiste tras reinicio PostgreSQL', count=='1')
        cmd(base + ['up','-d','--force-recreate','--no-deps','api','web'])
        wait_http()
        check('Proxy recupera API tras recreación', True)
        for _ in range(45):
            try:
                if request('/')[0]==200:break
            except OSError:pass
            time.sleep(1)
        else:raise AssertionError('Web no recuperó')
        check('Proxy recupera web tras recreación', True)
        report['backend_dependencies'] = cmd(base + ['exec','-T','api','pip','freeze']).splitlines()
        report['response'] = data
        report['status'] = 'passed'
    except Exception as error:
        report['status']='failed'; report['error']=str(error)
        raise
    finally:
        if not args.keep or report['status'] != 'passed':
            try:
                cmd(base + ['down','--volumes','--remove-orphans'])
                report['cleanup']='passed'
            except Exception as error:
                report['cleanup']=str(error)
        else:
            report['cleanup']='pending: kept for browser verification'
        empty_env.unlink(missing_ok=True)
        report['finished_utc']=datetime.now(timezone.utc).isoformat()
        report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print('Informe:', report_file, flush=True)
    print('URL:',report['url'], flush=True)

if __name__ == '__main__':
    main()
