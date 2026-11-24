const root=document.documentElement;
const theme=document.getElementById("theme");
const media=matchMedia("(prefers-color-scheme: dark)");
function currentTheme(){return root.dataset.theme || (media.matches?"dark":"light");}
function paintTheme(){
  const dark=currentTheme()==="dark";
  theme.setAttribute("aria-label",dark?"Switch to light mode":"Switch to dark mode");
  document.getElementById("theme-icon").setAttribute("d",dark?"M16 12a4 4 0 1 1-8 0 4 4 0 1 1 8 0ZM12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4":"M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5Z");
}
try {const saved=localStorage.getItem("scansafe-theme");if(["light","dark"].includes(saved))root.dataset.theme=saved;}catch{}
theme.hidden=false; paintTheme();
theme.addEventListener("click",()=>{root.dataset.theme=currentTheme()==="dark"?"light":"dark";try{localStorage.setItem("scansafe-theme",root.dataset.theme);}catch{}paintTheme();});
media.addEventListener("change",paintTheme);
