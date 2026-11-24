const video=document.getElementById("film");
document.getElementById("watch").addEventListener("click",()=>video.play().catch(()=>{}));
document.getElementById("chapters").hidden=false;
for(const button of document.querySelectorAll("[data-seconds]")){
  button.addEventListener("click",()=>{video.currentTime=Number(button.dataset.seconds);video.play().catch(()=>video.focus());});
}
const samples={
  baseline:["The Google address scored zero. None of the rules found a warning sign.","Phone screenshot of the Google baseline with a SAFE verdict and score 0."],
  lookalike:["A digit 1 replaced the final letter in PayPal. The lookalike domain and the word “login” raised the score to 5.","Phone screenshot showing a SUSPICIOUS verdict for a lookalike address, score 5."],
  warning:["The phone flagged three clues: HTTP, a .xyz domain, and “verify” in the address. Together they produced a score of 6.","Phone screenshot with a HIGH RISK verdict, score 6, and the three findings."]
};
const choices=document.getElementById("sample-options");
choices.hidden=false;
for(const button of choices.querySelectorAll("button")){
  button.addEventListener("click",()=>{
    const key=button.dataset.sample, [description,alt]=samples[key];
    const img=document.getElementById("sample-image");img.alt=alt;img.src="images/"+key+".jpg";
    document.getElementById("sample-copy").textContent=description;
    for(const other of choices.querySelectorAll("button")) other.setAttribute("aria-pressed",String(other===button));
  });
}

