window.MaterialHubWorkspace={
  filters:{},
  setFilter(key,value){this.filters[key]=value;document.dispatchEvent(new CustomEvent('mh:filter',{detail:this.filters}));},
  quickAction(url){window.location.href=url;},
  toast(message){const el=document.createElement('div');el.textContent=message;el.style='position:fixed;right:20px;bottom:20px;background:#172033;color:white;padding:12px 16px;border-radius:10px;z-index:9999';document.body.appendChild(el);setTimeout(()=>el.remove(),2600);}
};
