const steps = [['play','Play button'],['servers_tab','Servers tab'],['internet_tab','Internet tab'],['direct_connect','Direct Connect'],['ip_field','IP:port field'],['connect_button','Connect button']];
let state={calibrated:false,servers:[],points:{}}, calIndex=0;
const $=id=>document.getElementById(id);
function openView(name){document.querySelectorAll('.view').forEach(v=>v.classList.add('hidden'));$('view-'+name).classList.remove('hidden');document.querySelectorAll('.nav').forEach(n=>n.classList.toggle('active',n.dataset.view===name));}
document.querySelectorAll('.nav').forEach(n=>n.onclick=()=>openView(n.dataset.view));
function togglePanel(button){button.parentElement.classList.toggle('open')}
function log(text,muted=false){const line=document.createElement('div');line.className='log-line'+(muted?' muted':'');line.textContent=text;$('log').prepend(line)}
function toast(text){$('toast').textContent=text;$('toast').classList.add('show');setTimeout(()=>$('toast').classList.remove('show'),3500)}
function render(){const list=$('servers');list.innerHTML='';state.servers.forEach(s=>{const o=document.createElement('option');o.value=s;list.appendChild(o)});$('topState').textContent=state.calibrated?'CALIBRATED':'SETUP REQUIRED';calIndex=0;showCal()}
function showCal(){const [name,title]=steps[calIndex]||[];if(!name){$('calTitle').textContent='Calibration complete';$('calText').textContent='This computer is ready for background joining.';$('calCount').textContent='6 / 6';$('calBar').style.width='100%';return} $('calTitle').textContent=`Step ${calIndex+1} of 6 · ${title}`;$('calCount').textContent=`${calIndex} / 6`;$('calBar').style.width=`${calIndex/6*100}%`;$('calText').textContent=`Hover your mouse over SCP:SL’s ${title}, then click Capture. Do not click the game itself.`}
async function capturePoint(){if(!window.pywebview)return;const pos=await pywebview.api.get_cursor();if(!pos)return toast('Could not read the mouse position.');state.points[steps[calIndex][0]]=pos;calIndex++;if(calIndex===steps.length){state=await pywebview.api.save_calibration(state.points);toast('Calibration saved for this computer.')}showCal();render()}
async function startJoin(){const name=$('server').value.trim();if(!name)return toast('Choose or type a saved server first.');if(!state.calibrated)return toast('Calibrate this computer first.');$('feedState').textContent='RUNNING';$('topState').textContent='RUNNING';log(`Starting queue for ${name}`);await pywebview.api.start_join(name)}
async function beginRemember(){if(!window.pywebview)return;log('Watching Player.log — join a server normally now.');$('feedState').textContent='WATCHING';toast('Join a server normally in SCP:SL.');await pywebview.api.begin_remember()}
function status(text,running){$('feedState').textContent=running?'RUNNING':'IDLE';if(text)log(text);if(!running)$('topState').textContent='READY'}
function finished(result){status(result,false);log(`Finished: ${result}`);toast(result==='success'?'Joined successfully':`Run finished: ${result}`)}
function serverDetected(ip,port){const name=prompt(`Name this server (${ip}:${port})`);if(name&&window.pywebview)pywebview.api.save_server(name,ip,port).then(next=>{state=next;render();$('server').value=name;toast('Server saved')})}
window.addEventListener('pywebviewready',()=>pywebview.api.get_state().then(next=>{state=next;render()}));
