const get = id => document.getElementById(id);
const form = get("scan-form"), address = get("address"), camera = get("camera"), preview = get("camera-view");
const statusLine = get("status"), result = get("result");
const samples = [...document.querySelectorAll("[data-example]")];
let worker, busy = false, stream, cameraRequest = 0, cameraActive = false, frame;
const buffer = document.createElement("canvas");
const ctx = buffer.getContext("2d", {willReadFrequently: true});
function stopCamera() {
  cameraRequest++; cameraActive=false;
  cancelAnimationFrame(frame);
  stream?.getTracks().forEach(track => track.stop());
  stream = null; preview.srcObject = null; preview.hidden = true;
  camera.textContent = "Scan QR Code"; camera.setAttribute("aria-pressed","false");
}
function setBusy(value) {
  busy = value;
  [get("submit"),camera,address,...samples].forEach(control => control.disabled = value);
  result.setAttribute("aria-busy",String(value));
}
function list(id, lines) {
  get(id).replaceChildren(...lines.map(text => {
    const item = document.createElement("li"); item.textContent = text; return item;
  }));
}
function showResult(data, url) {
  setBusy(false);
  if (data.error) {statusLine.textContent = data.error; return;}
  const r = data.result;
  result.dataset.level=r.level; get("level").textContent=r.level; get("score").textContent="Score "+r.score;
  get("tested-address").textContent=url; list("findings",r.findings); list("technical",r.technical);
  result.hidden=false; statusLine.textContent="Scan complete. "+r.level+", score "+r.score+".";
}
function isLink(value) {
  if (!value || value.length>4096 || /\s/.test(value)) return false;
  if (/^(blob|data|javascript|vbscript):.+/i.test(value)) return true;
  const webScheme=/^https?:\/\//i.test(value);
  if (!webScheme && !/^[^:/?#]+\.[^:/?#]+(:\d+)?([/?#]|$)/.test(value)) return false;
  try {return Boolean(new URL(webScheme?value:"https://"+value).hostname);}
  catch {return false;}
}
function scan(value) {
  if (busy) return;
  stopCamera();
  const url=value.trim(); address.value=url; result.hidden=true;
  if (!isLink(url)) {
    statusLine.textContent="Enter a link or scan a QR code containing a web address."; return;
  }
  setBusy(true); statusLine.textContent="Checking the link. The scanner may take a moment to load on your first scan.";
  try {
    worker ??= new Worker("worker.js");
    worker.onmessage=e=>showResult(e.data,url);
    worker.onerror=()=>{worker.terminate(); worker=null; showResult({error:"Could not start the scanner. Please try again."},url);};
    worker.postMessage(url);
  } catch {setBusy(false); statusLine.textContent="The browser could not start the scanner.";}
}
form.addEventListener("submit",event=>{event.preventDefault();scan(address.value);});
samples.forEach(button=>button.addEventListener("click",()=>scan(button.dataset.example)));
function decode(request) {
  if (cameraRequest!==request || !stream) return;
  if (preview.readyState>=2 && preview.videoWidth) {
    const scale=Math.min(1,720/Math.max(preview.videoWidth,preview.videoHeight));
    const w=Math.round(preview.videoWidth*scale),h=Math.round(preview.videoHeight*scale);
    if (buffer.width!==w || buffer.height!==h) {buffer.width=w; buffer.height=h;}
    ctx.drawImage(preview,0,0,w,h);
    const code=jsQR(ctx.getImageData(0,0,w,h).data,w,h);
    if (code?.data) {scan(code.data);return;}
  }
  frame=requestAnimationFrame(()=>decode(request));
}
camera.addEventListener("click",async()=>{
  if(cameraActive){stopCamera();statusLine.textContent="Camera stopped.";return;}
  if(!navigator.mediaDevices?.getUserMedia){statusLine.textContent="Camera access is unavailable. Paste a link or choose an example.";return;}
  const request=++cameraRequest; cameraActive=true; camera.textContent="Stop camera"; camera.setAttribute("aria-pressed","true");
  result.hidden=true; statusLine.textContent="Allow camera access to scan a QR code.";
  try {
    const media=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:"environment"}},audio:false});
    if(request!==cameraRequest){media.getTracks().forEach(track=>track.stop());return;}
    stream=media; preview.srcObject=stream; preview.hidden=false; await preview.play();
    if(request!==cameraRequest)return;
    statusLine.textContent="Point the camera at a QR code."; decode(request);
  } catch {
    if(request!==cameraRequest)return;
    stopCamera();statusLine.textContent="The camera could not start. Paste a link or choose an example.";
  }
});
document.addEventListener("visibilitychange",()=>{if(document.hidden && cameraActive){stopCamera();statusLine.textContent="Camera stopped.";}});
window.addEventListener("pagehide",stopCamera);

