(function(){
  'use strict';
  document.documentElement.classList.add('ss-motion');

  // Active navigation state.
  var current=(location.pathname.split('/').pop()||'index.html').toLowerCase();
  document.querySelectorAll('.nav-links a[href]').forEach(function(link){
    var href=(link.getAttribute('href')||'').split('#')[0].toLowerCase();
    if(href===current){link.setAttribute('aria-current','page');}
  });

  // Identify individual competition team pages for page-specific refinement.
  if(/^(mini|petite|junior|juniorettes|teen)-competition-team\.html$/.test(current)||current==='team-only.html'||current==='competition-auditions.html'){
    document.body.setAttribute('data-competition-team','true');
  }

  // Replace the homepage performance artwork with the Stage Starz video.
  var performanceArt=document.querySelector('.performance-art');
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
