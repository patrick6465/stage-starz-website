(function(){
  'use strict';
  document.documentElement.classList.add('ss-motion');
  var current=(location.pathname.split('/').pop()||'index.html').toLowerCase();
  var isHome=current==='index.html'||current===''||location.pathname==='/';
  if(isHome){document.body.setAttribute('data-homepage','true');}

  document.querySelectorAll('.nav-links a[href]').forEach(function(link){
    var href=(link.getAttribute('href')||'').split('#')[0].toLowerCase();
    if(href===current){link.setAttribute('aria-current','page');}
  });

  // Normalize old development-home links without changing the approved visual design.
  document.querySelectorAll('a[href="index-new.html"],a[href="index.html"]').forEach(function(link){link.setAttribute('href','/');});

  if(/^(mini|petite|junior|juniorettes|teen)-competition-team\.html$/.test(current)||current==='team-only.html'||current==='competition-auditions.html'){
    document.body.setAttribute('data-competition-team','true');
  }

  if(isHome){
    // Add local-market confidence immediately after the existing trust strip.
    var trust=document.querySelector('.trust-strip');
    if(trust&&!document.querySelector('.ss-local-proof')){
      var local=document.createElement('section');
      local.className='ss-local-proof';
      local.setAttribute('aria-label','Serving local dance families');
      local.innerHTML='<div class="ss-local-proof-inner"><div class="ss-local-proof-copy"><strong>Dance training close to home.</strong><span>Conveniently located in Temperance for families throughout southern Monroe County and the Toledo area.</span></div><div class="ss-local-proof-item">Temperance, MI<small>6800 Lewis Ave</small></div><div class="ss-local-proof-item">Ages 3+<small>Beginner through advanced</small></div><div class="ss-local-proof-item">Recreational + Competitive<small>A path for every dancer</small></div></div>';
      trust.insertAdjacentElement('afterend',local);
    }

    // Give mobile visitors a persistent, low-friction route to classes and help.
    if(!document.querySelector('.ss-mobile-cta')){
      var mobile=document.createElement('nav');
      mobile.className='ss-mobile-cta';
      mobile.setAttribute('aria-label','Quick actions');
      mobile.innerHTML='<a class="primary" href="classes.html">Find Classes</a><a class="secondary" href="contact.html">Ask a Question</a>';
      document.body.appendChild(mobile);
    }
  }

  var performanceArt=document.querySelector('.performance-art');
  if(performanceArt){
    performanceArt.style.background='#050505';
    var video=document.createElement('video');
    video.controls=true;video.playsInline=true;video.preload='metadata';
    video.setAttribute('aria-label','Stage Starz competition, recital, and community performance video');
    Object.assign(video.style,{position:'absolute',inset:'0',zIndex:'3',width:'100%',height:'100%',display:'block',objectFit:window.matchMedia('(max-width:640px)').matches?'contain':'cover',background:'#050505',opacity:'0',transition:'opacity .35s ease'});
    video.innerHTML='<source src="/assets/videos/stage-starz-homepage-performance-web.mp4" type="video/mp4">Your browser does not support HTML5 video.';
    var label=document.createElement('div');
    label.textContent='Competition • Recital • Community Performances';
    Object.assign(label.style,{position:'absolute',zIndex:'4',left:'25px',right:'25px',bottom:'58px',padding:'14px 16px',borderRadius:'18px',background:'rgba(9,5,20,.62)',color:'#fff',fontWeight:'900',backdropFilter:'blur(12px)',pointerEvents:'none',opacity:'0',transition:'opacity .35s ease'});
    video.addEventListener('loadedmetadata',function(){video.style.opacity='1';label.style.opacity='1';});
    video.addEventListener('error',function(){video.remove();label.remove();});
    performanceArt.appendChild(video);performanceArt.appendChild(label);
  }

  var targets=document.querySelectorAll('main > section, .section-head, .card, .panel, .program, .feature-card, .event-card, .testimonial-card, .jackrabbit-card');
  targets.forEach(function(el,index){el.classList.add('ss-reveal');el.dataset.delay=String(index%4);});
  if(!('IntersectionObserver' in window)){targets.forEach(function(el){el.classList.add('ss-visible');});return;}
  var observer=new IntersectionObserver(function(entries){entries.forEach(function(entry){if(entry.isIntersecting){entry.target.classList.add('ss-visible');observer.unobserve(entry.target);}});},{threshold:.08,rootMargin:'0px 0px -35px 0px'});
  targets.forEach(function(el){observer.observe(el);});
})();
