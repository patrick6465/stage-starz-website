(function(){
  'use strict';
  document.documentElement.classList.add('ss-motion');

  // Active navigation state.
  var current=(location.pathname.split('/').pop()||'index.html').toLowerCase();
  document.querySelectorAll('.nav-links a[href]').forEach(function(link){
    var href=(link.getAttribute('href')||'').split('#')[0].toLowerCase();
    if(href===current){link.setAttribute('aria-current','page');}
  });

  // Short-term enrollment alert for the homepage as the 2026-2027 season begins.
  if(current==='index.html'&&!document.querySelector('.ss-season-alert')){
    var topbar=document.querySelector('.topbar');
    var header=document.querySelector('.header');
    var seasonAlert=document.createElement('section');
    seasonAlert.className='ss-season-alert';
    seasonAlert.setAttribute('aria-label','Class enrollment announcement');
    seasonAlert.innerHTML=
      '<div class="ss-season-alert-inner">'+
        '<div class="ss-season-alert-copy">'+
          '<strong>Classes Begin Monday — Limited Openings Still Available</strong>'+
          '<span>Find the right class for your dancer and get started with Stage Starz.</span>'+
        '</div>'+
        '<div class="ss-season-alert-actions">'+
          '<a href="class-finder.html">Find Your Class</a>'+
          '<a href="classes.html">Register Now</a>'+
        '</div>'+
      '</div>';

    var seasonStyle=document.createElement('style');
    seasonStyle.textContent=
      '.ss-season-alert{position:relative;z-index:95;background:linear-gradient(100deg,#691170,#a91cae 48%,#007f88);color:#fff;border-bottom:1px solid rgba(255,255,255,.2);box-shadow:0 10px 28px rgba(8,7,19,.2)}'+
      '.ss-season-alert-inner{width:min(1180px,94%);margin:0 auto;padding:15px 20px;display:flex;align-items:center;justify-content:space-between;gap:22px}'+
      '.ss-season-alert-copy{display:flex;flex-direction:column;gap:2px;line-height:1.3}'+
      '.ss-season-alert-copy strong{font-size:clamp(1rem,2vw,1.22rem);font-weight:950;letter-spacing:-.015em}'+
      '.ss-season-alert-copy span{font-size:.92rem;color:rgba(255,255,255,.88)}'+
      '.ss-season-alert-actions{display:flex;gap:9px;flex:0 0 auto}'+
      '.ss-season-alert-actions a{display:inline-flex;align-items:center;justify-content:center;min-height:42px;padding:10px 16px;border-radius:999px;font-size:.9rem;font-weight:900;text-decoration:none;white-space:nowrap}'+
      '.ss-season-alert-actions a:first-child{color:#fff;border:1px solid rgba(255,255,255,.58);background:rgba(7,5,16,.18)}'+
      '.ss-season-alert-actions a:last-child{color:#23102b;background:#fff;box-shadow:0 8px 20px rgba(0,0,0,.18)}'+
      '.ss-season-alert-actions a:hover{transform:translateY(-1px)}'+
      '@media(max-width:760px){.ss-season-alert-inner{padding:13px 14px;flex-direction:column;text-align:center;gap:10px}.ss-season-alert-copy span{font-size:.86rem}.ss-season-alert-actions{width:100%;justify-content:center}.ss-season-alert-actions a{flex:1;max-width:180px}}'+
      '@media(max-width:390px){.ss-season-alert-actions{flex-direction:column;align-items:stretch}.ss-season-alert-actions a{max-width:none;width:100%}}';
    document.head.appendChild(seasonStyle);

    if(header&&header.parentNode){
      header.parentNode.insertBefore(seasonAlert,header);
    }else if(topbar&&topbar.parentNode){
      topbar.insertAdjacentElement('afterend',seasonAlert);
    }
  }

  // Force the homepage Stardust Ship-it-Shop banner to use the animated media.
  // Keep the existing static image visible until the animation is actually ready,
  // so shoppers always have a working clickable banner even if media loading fails.
  var shopLink=document.querySelector('.approved-shop-link');
  var shopBanner=shopLink&&shopLink.querySelector('img');
  if(shopLink&&shopBanner&&!shopLink.querySelector('.ss-approved-shop-video')){
    var shopVideo=document.createElement('video');
    shopVideo.className='ss-approved-shop-video';
    shopVideo.autoplay=true;
    shopVideo.muted=true;
    shopVideo.defaultMuted=true;
    shopVideo.loop=true;
    shopVideo.playsInline=true;
    shopVideo.preload='auto';
    shopVideo.setAttribute('muted','');
    shopVideo.setAttribute('playsinline','');
    shopVideo.setAttribute('aria-hidden','true');
    shopVideo.innerHTML='<source src="/assets/media/stardust-ship-it-shop.mp4?v=20260825-1" type="video/mp4">';
    Object.assign(shopVideo.style,{
      display:'none',
      width:'100%',
      height:'auto',
      objectFit:'cover',
      objectPosition:'center',
      pointerEvents:'none'
    });
    shopBanner.insertAdjacentElement('afterend',shopVideo);

    function showAnimatedShopBanner(){
      shopVideo.style.display='block';
      shopBanner.style.display='none';
      var playPromise=shopVideo.play();
      if(playPromise&&playPromise.catch){playPromise.catch(function(){});}
    }
    shopVideo.addEventListener('canplay',showAnimatedShopBanner,{once:true});
    shopVideo.addEventListener('loadeddata',showAnimatedShopBanner,{once:true});
    shopVideo.addEventListener('error',function(){
      shopVideo.remove();
      shopBanner.style.display='block';
    },{once:true});
    shopVideo.load();
  }

  // Identify individual competition team pages for page-specific refinement.
  if(/^(mini|petite|junior|juniorettes|teen)-competition-team\.html$/.test(current)||current==='team-only.html'||current==='competition-auditions.html'){
    document.body.setAttribute('data-competition-team','true');
  }

  // Replace the homepage performance artwork with the legacy fallback video only
  // when the managed Website Video player has not already replaced the artwork.
  var performanceArt=document.querySelector('.performance-art:not(.ss-home-performance-video)');
  if(performanceArt){
    performanceArt.style.background='#050505';
    var video=document.createElement('video');
    video.controls=true;
    video.playsInline=true;
    video.preload='metadata';
    video.setAttribute('aria-label','Stage Starz competition, recital, and community performance video');
    Object.assign(video.style,{
      position:'absolute',inset:'0',zIndex:'3',width:'100%',height:'100%',
      display:'block',objectFit:window.matchMedia('(max-width:640px)').matches?'contain':'cover',
      background:'#050505',opacity:'0',transition:'opacity .35s ease'
    });
    video.innerHTML='<source src="/assets/videos/stage-starz-homepage-performance-web.mp4" type="video/mp4">Your browser does not support HTML5 video.';

    var label=document.createElement('div');
    label.textContent='Competition • Recital • Community Performances';
    Object.assign(label.style,{
      position:'absolute',zIndex:'4',left:'25px',right:'25px',bottom:'58px',
      padding:'14px 16px',borderRadius:'18px',background:'rgba(9,5,20,.62)',
      color:'#fff',fontWeight:'900',backdropFilter:'blur(12px)',pointerEvents:'none',
      opacity:'0',transition:'opacity .35s ease'
    });

    video.addEventListener('loadedmetadata',function(){video.style.opacity='1';label.style.opacity='1';});
    video.addEventListener('error',function(){video.remove();label.remove();});
    performanceArt.appendChild(video);
    performanceArt.appendChild(label);
  }

  // Reveal major content groups, but not navigation or live Jackrabbit rows.
  var targets=document.querySelectorAll('main > section, .section-head, .card, .panel, .program, .feature-card, .event-card, .testimonial-card, .jackrabbit-card');
  targets.forEach(function(el,index){
    el.classList.add('ss-reveal');
    el.dataset.delay=String(index%4);
  });

  if(!('IntersectionObserver' in window)){
    targets.forEach(function(el){el.classList.add('ss-visible');});
    return;
  }
  var observer=new IntersectionObserver(function(entries){
    entries.forEach(function(entry){
      if(entry.isIntersecting){
        entry.target.classList.add('ss-visible');
        observer.unobserve(entry.target);
      }
    });
  },{threshold:.08,rootMargin:'0px 0px -35px 0px'});
  targets.forEach(function(el){observer.observe(el);});
})();