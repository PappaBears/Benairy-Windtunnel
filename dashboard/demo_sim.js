/* Benairy in-browser simulator. Mirrors sim/server.py so the dashboard runs with no
   server at all: it replaces window.fetch for /api/... paths when the real API is
   unreachable (or when the page is opened with #demo). Demo data is simulated. */
(function(){
const q0=50.0, S=0.0028, CLA=0.075, CLMAX=0.85, CD0=0.030, EAR=0.9*Math.PI*2.29, STRUT=0.08*0.0045*0.050, NPC=1e-6, CROSS=0.02;
const C=0.01, DELTA=0.137, TAU1=0.87;
let rnd=(function(s){return function(){s=(s*1664525+1013904223)%4294967296;return s/4294967296;};})(7);
const gauss=(sd)=>{let u=1-rnd(),v=rnd();return sd*Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*v);};
function coeff(a){let cl=CLA*a;if(Math.abs(cl)>CLMAX)cl=Math.sign(cl)*(CLMAX-0.02*(Math.abs(a)-CLMAX/CLA));return [cl,CD0+cl*cl/EAR];}
function tunnelCoeff(a){const d=DELTA*S/C,vol=0.7*S*0.12*0.035,esb=TAU1*vol/Math.pow(C,1.5);let [clu,cdu]=coeff(a);
  for(let i=0;i<3;i++){const da=d*clu*180/Math.PI;const [clf,cdf]=coeff(a+da);const ewb=(S/(4*C))*cdu,eps=esb+ewb;clu=clf/(1-2*eps);cdu=(cdf-d*clu*clu)/(1-3*esb-2*ewb);}return [clu,cdu];}
const cfg={m11:1e-6,m12:0,m21:0,m22:1e-6,kq:1.067,p_station_pa:101325,aoa_zero_deg:0,aoa_sign:1,servo_gain:1,servo_offset_deg:0,lift_limit_n:1.5,drag_limit_n:0.8,fan_slew_up:0.25,aoa_min:-30,aoa_max:30,client_timeout_s:10,vbus_min_v:10.5,stall_rpm:300,stall_grace_s:3,led_brightness:0.4,led_on:1};
const st={state:'IDLE',faults:new Set(),fan_cmd:0,fan_out:0,aoa_cmd:0,aoa_true:0,raw0:[0,0],dp0:0,tared:false,taring:null,seq:0,ring:[],tel:null,sweep:null,list:[],i:-1,pts:[],settle:0,acc:[],t:0,hx:0,drift:0,estop:false,fan_fail:false,stall:0,lastClient:null,weight:0.08,aoaZero:137.2};
function fault(n){st.faults.add(n);st.state='FAULT';st.fan_cmd=st.fan_out=0;st.sweep=null;st.i=-1;}
function tick(dt){st.t+=dt;
  if(st.state!=='FAULT'){st.fan_out=st.fan_cmd>st.fan_out?Math.min(st.fan_cmd,st.fan_out+cfg.fan_slew_up*dt):st.fan_cmd;}
  st.aoa_true+=(st.aoa_cmd-st.aoa_true)*Math.min(1,dt/0.25);st.drift+=gauss(0.3)*dt;
  const q=q0*st.fan_out*st.fan_out,[cl,cd]=tunnelCoeff(st.aoa_true),lift=q*S*cl,drag=q*S*cd+q*STRUT;
  st.hx+=dt;if(st.hx<0.1)return;st.hx-=0.1;
  const lr=Math.round(123456+(lift-st.weight+CROSS*drag)/NPC+st.drift+gauss(12)),dr=Math.round(-98765+drag/NPC+st.drift*0.5+gauss(12));
  const dp=q/1.067+0.8+gauss(0.05),temp=21.5+0.3*Math.sin(st.t/60),araw=(st.aoaZero+st.aoa_true+gauss(0.05))%360,rpm=st.fan_fail?0:(st.fan_out>0.05?8000*st.fan_out+gauss(20):0);
  if(st.taring){st.taring.l.push(lr);st.taring.d.push(dr);st.taring.dp.push(dp);if(st.t-st.taring.t0>=2){const m=a=>a.reduce((x,y)=>x+y,0)/a.length;st.raw0=[m(st.taring.l),m(st.taring.d)];st.dp0=m(st.taring.dp);st.tared=true;st.taring=null;}}
  const dl=lr-st.raw0[0],dd=dr-st.raw0[1],ln=cfg.m11*dl+cfg.m12*dd,dn=cfg.m21*dl+cfg.m22*dd,dpm=dp-st.dp0,qm=cfg.kq*dpm,rho=cfg.p_station_pa/(287.05*(temp+273.15));
  let a=((araw-cfg.aoa_zero_deg+180)%360+360)%360-180;st.seq++;
  st.tel={seq:st.seq,t_ms:Math.round(st.t*1000),state:st.state,faults:'',fan_cmd:st.fan_cmd,fan_out:st.fan_out,fan_rpm:rpm,aoa_cmd:st.aoa_cmd,aoa_deg:cfg.aoa_sign*a,aoa_raw:araw,lift_raw:lr,drag_raw:dr,lift_n:ln,drag_n:dn,dp_pa:dpm,q_pa:qm,v_ms:Math.sqrt(Math.max(0,2*qm/rho)),temp_c:temp,rho:rho,vbus:12.1,tared:st.tared?1:0};
  st.ring.push(st.tel);if(st.ring.length>200)st.ring.shift();
  if(st.estop)fault('ESTOP');if(Math.abs(ln)>cfg.lift_limit_n)fault('OVERLOAD_LIFT');if(Math.abs(dn)>cfg.drag_limit_n)fault('OVERLOAD_DRAG');
  if(st.fan_out>0.25&&rpm<cfg.stall_rpm)st.stall+=0.1;else st.stall=0;if(st.stall>cfg.stall_grace_s)fault('FAN_STALL');
  if(st.sweep&&st.state==='SWEEP'){const ready=Math.abs(st.fan_out-st.fan_cmd)<1e-6;
    if(st.settle<st.sweep.settle||!ready){if(ready)st.settle+=0.1;}
    else{st.acc.push(Object.assign({},st.tel));if(st.acc.length>=st.sweep.samples){st.pts.push(point());st.acc=[];st.i++;
      if(st.i>=st.list.length){st.sweep=null;st.i=-1;st.fan_cmd=0;st.state='IDLE';}else{st.aoa_cmd=clamp(st.list[st.i]);st.settle=0;}}}}
  st.tel.state=st.state;st.tel.faults=[...st.faults].sort().join(',');
}
const clamp=v=>Math.max(cfg.aoa_min,Math.min(cfg.aoa_max,v));
function point(){const A=st.acc,n=A.length,mean=k=>A.reduce((s,a)=>s+a[k],0)/n,sd=k=>{const m=mean(k);return n>1?Math.sqrt(A.reduce((s,a)=>s+(a[k]-m)**2,0)/(n-1)):0;};const q=mean('q_pa'),rho=mean('rho');
  return {aoa_cmd:st.list[st.i],aoa_deg:mean('aoa_deg'),aoa_sd:sd('aoa_deg'),fan_cmd:st.fan_cmd,fan_rpm:mean('fan_rpm'),q_pa:q,q_sd:sd('q_pa'),v_ms:Math.sqrt(Math.max(0,2*q/rho)),temp_c:mean('temp_c'),rho:rho,lift_n:mean('lift_n'),lift_sd:sd('lift_n'),drag_n:mean('drag_n'),drag_sd:sd('drag_n'),lift_raw:Math.round(mean('lift_raw')),drag_raw:Math.round(mean('drag_raw')),n:n};}
function leds(){const B=Math.max(0,Math.min(1,cfg.led_brightness))*(cfg.led_on>0.5?1:0),ph=0.5+0.5*Math.sin(st.t*2*Math.PI);let out='';
  for(let i=0;i<24;i++){let k,c;if(st.state==='FAULT'){k=B*(Math.floor(st.t*4)%2?1:0.15);c=[1,0.1,0.15];}else if(st.taring){k=B*(0.3+0.7*ph);c=[0.93,0.96,1];}
    else if(st.state==='SWEEP'){const prog=st.i/Math.max(1,st.list.length);if((i+0.5)/24<=prog){k=B;c=[1,0.78,0.43];}else{k=B*0.7;c=[0.4,0.89,1];}}
    else if(st.state==='RUNNING'){k=B*(0.5+0.5*st.fan_out);c=[0.4,0.89,1];}else{k=B*0.35;c=[0.55,0.7,0.85];}
    out+=c.map(v=>('0'+Math.round(255*Math.min(1,v*k)).toString(16)).slice(-2)).join('');}return out;}
function cmd(p){const g=(k,d=0)=>parseFloat(p.get(k)??d);const c=p.get('cmd');
  switch(c){
    case 'fan':if(st.state==='FAULT')return[400,'fault active: clear faults first'];if(st.state==='SWEEP')return[400,'sweep running: stop it first'];st.fan_cmd=Math.max(0,Math.min(1,g('value')));st.state=st.fan_cmd>0?'RUNNING':'IDLE';return[200,'ok'];
    case 'aoa':if(st.state==='SWEEP')return[400,'sweep running'];st.aoa_cmd=clamp(g('value'));return[200,'ok'];
    case 'tare':if(st.fan_out>0.02)return[400,'fan must be off (wind-off tare)'];st.taring={t0:st.t,l:[],d:[],dp:[]};return[200,'taring 2 s'];
    case 'zero_aoa':cfg.aoa_zero_deg=st.tel?st.tel.aoa_raw:0;return[200,'ok'];
    case 'stop':st.fan_cmd=st.fan_out=0;if(st.state!=='FAULT')st.state='IDLE';st.sweep=null;st.i=-1;return[200,'stopped'];
    case 'clear_faults':if(st.estop)return[400,'stop loop is open'];st.faults.clear();st.state='IDLE';st.fan_cmd=st.fan_out=0;st.stall=0;return[200,'ok'];
    case 'light':cfg.led_on=(p.get('value')==='0')?0:1;return[200,'ok'];
    case 'set':{const k=p.get('key');if(!(k in cfg))return[400,'unknown key'];cfg[k]=g('value');return[200,'ok'];}
    case 'sweep':{if(st.state==='FAULT')return[400,'fault active'];if(!st.tared)return[400,'tare first (wind off)'];const aoas=(p.get('list')||'').split(',').map(s=>parseFloat(s)).filter(x=>!isNaN(x));if(!aoas.length)return[400,'empty list'];
      let lst=aoas.slice();if(p.get('updown')==='1')lst=lst.concat(aoas.slice(0,-1).reverse());st.sweep={fan:Math.max(0,Math.min(1,g('fan'))),settle:g('settle',2),samples:parseInt(p.get('samples')||'40')};st.list=lst;st.pts=[];st.i=0;st.settle=0;st.acc=[];st.fan_cmd=st.sweep.fan;st.aoa_cmd=clamp(lst[0]);st.state='SWEEP';return[200,'ok'];}
  }return[400,'unknown command'];}
const csvHdr='point,aoa_cmd_deg,aoa_deg,aoa_sd_deg,fan_cmd,fan_rpm,q_pa,q_sd_pa,v_ms,temp_c,rho_kgm3,lift_n,lift_sd_n,drag_n,drag_sd_n,lift_raw,drag_raw,n\n';
function csv(){return csvHdr+st.pts.map((p,i)=>[i,p.aoa_cmd.toFixed(3),p.aoa_deg.toFixed(3),p.aoa_sd.toFixed(3),p.fan_cmd.toFixed(3),p.fan_rpm.toFixed(0),p.q_pa.toFixed(3),p.q_sd.toFixed(3),p.v_ms.toFixed(3),p.temp_c.toFixed(2),p.rho.toFixed(4),p.lift_n.toFixed(6),p.lift_sd.toFixed(6),p.drag_n.toFixed(6),p.drag_sd.toFixed(6),p.lift_raw,p.drag_raw,p.n].join(',')).join('\n')+(st.pts.length?'\n':'');}
function status(){const t=Object.assign({},st.tel||{seq:0,state:st.state,faults:''});t.sweep_i=st.sweep?st.i:-1;t.sweep_n=st.sweep?st.list.length:0;t.sweep_points=st.pts.length;t.leds=leds();delete t.aoa_raw;return t;}
const R=(code,body,type)=>Promise.resolve(new Response(typeof body==='string'?body:JSON.stringify(body),{status:code,headers:{'Content-Type':type||'application/json'}}));
let timer=null;
window.BenairyDemo={
  start(){if(timer)return;timer=setInterval(()=>{for(let k=0;k<2;k++)tick(0.01);},20);
    const real=window.fetch.bind(window);
    window.fetch=function(url,opt){const u=String(url);if(!u.includes('/api/'))return real(url,opt);const path=u.split('/api/')[1].split('?')[0];const qs=new URLSearchParams(u.split('?')[1]||'');
      if(path==='status')return R(200,status());if(path==='samples'){const since=parseInt(qs.get('since')||'0');return R(200,st.ring.filter(s=>s.seq>since).map(s=>({seq:s.seq,t_ms:s.t_ms,lift_n:s.lift_n,drag_n:s.drag_n,q_pa:s.q_pa,aoa_deg:s.aoa_deg,fan_rpm:s.fan_rpm})));}
      if(path==='config')return R(200,cfg);if(path==='sweep.csv')return R(200,csv(),'text/csv');if(path==='sweep.json')return R(200,st.pts);
      if(path==='info')return R(200,{name:'Benairy',vendor:'Schreiber AI',fw:'browser-sim-0.1.0',sim:true});
      if(path==='cmd'){const p=new URLSearchParams(opt&&opt.body?String(opt.body):'');const [c,m]=cmd(p);return R(c,m,'text/plain');}
      if(path==='sim'){const p=new URLSearchParams(opt&&opt.body?String(opt.body):'');if(p.has('estop'))st.estop=p.get('estop')==='1';if(p.has('fan_fail'))st.fan_fail=p.get('fan_fail')==='1';return R(200,'ok','text/plain');}
      return R(404,'not found','text/plain');};},
  inject(k,v){const p=new URLSearchParams();p.set(k,v);return window.fetch('/api/sim',{method:'POST',body:p});},
  active:()=>!!timer};
})();
