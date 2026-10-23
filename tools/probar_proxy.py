"""Prueba Docker del proxy local y TLS con upstreams ficticios, sin tocar la VM."""
import argparse, http.client, json, os, pathlib, shutil, ssl, subprocess, tempfile, time, uuid

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--openssl',default='openssl')
    parser.add_argument('--report',required=True)
    args=parser.parse_args()
    repo=pathlib.Path(__file__).resolve().parents[1]
    report={'pruebas':[], 'alcance':'Nginx real y TLS con certificado temporal; upstreams ficticios. No prueba VM ni certificado publico.'}
    tag='pr22-'+uuid.uuid4().hex[:8]; containers=[]; network=False
    def run(*cmd,check=True,env=None):
        p=subprocess.run(cmd,cwd=repo,env=env,text=True,capture_output=True)
        if check and p.returncode: raise RuntimeError(p.stderr or p.stdout)
        return p
    def docker(*cmd,**kw):return run('docker',*cmd,**kw)
    def record(name):report['pruebas'].append(name); print('OK '+name,flush=True)
    try:
      with tempfile.TemporaryDirectory(prefix='pr22-') as tmp:
        root=pathlib.Path(tmp); cert=root/'cert/live/communitylab.nodnexa.com'; cert.mkdir(parents=True)
        run(args.openssl,'req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=localhost',
            '-addext','subjectAltName=DNS:localhost,DNS:communitylab.nodnexa.com','-keyout',str(cert/'privkey.pem'),'-out',str(cert/'fullchain.pem'))
        env={k:v for k,v in os.environ.items() if not k.startswith(('POSTGRES_','HTTP','LETSENCRYPT','DOCKER_PLATFORM','WORKER_MODE','GEMINI_'))}
        env.update(POSTGRES_PASSWORD='isolated_test_only',WORKER_MODE='simulado',DOCKER_PLATFORM='linux/amd64',
                   HTTP_PORT='18080',HTTP_BIND_ADDRESS='127.0.0.1',LETSENCRYPT_DIR=str(root/'cert'),HTTPS_HTTP_PORT='18081',HTTPS_PORT='18443',HTTPS_BIND_ADDRESS='127.0.0.1')
        empty=root/'empty.env'; empty.write_text('')
        base=['compose','--env-file',str(empty),'-f','docker-compose.yml']
        local=json.loads(docker(*base,'config','--format','json',env=env).stdout)['services']['proxy']
        tls=json.loads(docker(*base,'-f','compose.https.yml','config','--format','json',env=env).stdout)['services']['proxy']
        assert [(p['published'],p['target'],p['host_ip']) for p in local['ports']]==[('18080',80,'127.0.0.1')]
        assert len(local['volumes'])==1
        assert {p['published'] for p in tls['ports']}=={'18081','18443'}
        assert len(tls['volumes'])==2
        assert next(v for v in tls['volumes'] if v['target']=='/etc/nginx/conf.d/default.conf')['source'].endswith('nginx.https.conf')
        record('Compose: puertos configurables; TLS reemplaza HTTP y montajes sin duplicados')
        missing=docker('run','--rm','--network','none','--mount',f'type=bind,source={repo / "proxy/nginx.https.conf"},target=/etc/nginx/conf.d/default.conf,readonly','nginx:stable-alpine','nginx','-t',check=False)
        assert missing.returncode and 'cannot load certificate' in missing.stderr
        record('HTTPS rechaza certificados ausentes; no hay degradacion silenciosa')
        docker('network','create',tag); network=True
        upstream=root/'upstream.conf'
        upstream.write_text('server { listen 3000; listen 8000; location / { default_type application/json; return 200 \'{"uri":"$request_uri","proto":"$http_x_forwarded_proto"}\'; } }\n')
        containers.append(tag+'-upstream')
        docker('run','-d','--name',containers[-1],'--network',tag,'--network-alias','web','--network-alias','api','--mount',f'type=bind,source={upstream},target=/etc/nginx/conf.d/default.conf,readonly','nginx:stable-alpine')
        for mode,config in [('local',local),('tls',tls)]:
            name=tag+'-'+mode; containers.append(name)
            cmd=['run','-d','--name',name,'--network',tag,'-p','127.0.0.1::80']
            if mode=='tls':cmd+=['-p','127.0.0.1::443']
            for v in config['volumes']:cmd+=['--mount',f'type=bind,source={v["source"]},target={v["target"]},readonly']
            docker(*cmd,'nginx:stable-alpine')
            docker('exec',name,'nginx','-t')
            ports=json.loads(docker('inspect',name).stdout)[0]['NetworkSettings']['Ports']
            httpport=int(ports['80/tcp'][0]['HostPort'])
            def request(path,tls_request=False):
                for attempt in range(20):
                    try:
                        if tls_request:
                            context=ssl.create_default_context(cafile=str(cert/'fullchain.pem'))
                            c=http.client.HTTPSConnection('localhost',int(ports['443/tcp'][0]['HostPort']),context=context,timeout=3)
                        else:c=http.client.HTTPConnection('localhost',httpport,timeout=3)
                        c.request('GET',path);r=c.getresponse();data=r.read();headers=dict(r.getheaders());c.close()
                        return r.status,headers,data
                    except (OSError,http.client.HTTPException):
                        if attempt==19:raise
                        time.sleep(.2)
            assert request('/healthz')[0]==200
            if mode=='tls':
                status,headers,_=request('/ruta?x=1')
                assert status==301 and headers['Location']=='https://communitylab.nodnexa.com/ruta?x=1'
                record('HTTP de VM redirige a HTTPS conservando ruta y query')
            for path in ('/','/api/mensajes?test=1'):
                status,headers,data=request(path,mode=='tls')
                assert status==200 and json.loads(data)=={'uri':path,'proto':'https' if mode=='tls' else 'http'}
                if mode=='tls':
                    assert headers['Strict-Transport-Security']=='max-age=31536000'
                    assert headers['X-Content-Type-Options']=='nosniff'
                else:assert 'Location' not in headers
            record(mode+': nginx -t, health, web, API, query y protocolo reenviado correctos')
        record('TLS verificado con CA temporal y nombre localhost, sin desactivar verificacion SSL')
        report['correcto']=True
    except Exception as exc:
        report.update(correcto=False,error=str(exc)); raise
    finally:
        for name in reversed(containers):docker('rm','-f',name,check=False)
        if network:docker('network','rm',tag,check=False)
        pathlib.Path(args.report).resolve().write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')

if __name__=='__main__':main()
