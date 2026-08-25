(function(){
  'use strict';
  document.documentElement.classList.add('ss-motion');
  var current=(location.pathname.split('/').pop()||'index.html').toLowerCase();
  var isHome=current==='index.html'||current===''||location.pathname==='/';
  var isRegistration=/^(preschool|primary|elementary|intermediate-advanced|specialized)-class-registration\.html$/.test(current);
  if(isHome){document.body.setAttribute('data-homepage','true');}
  if(isRegistration){document.body.setAttribute('data-registration-page','true');}

  document.querySelectorAll('.nav-links a[href]').forEach(function(link){
    var href=(link.getAttribute('href')||'').split('#')[0].toLowerCase();
    if(href===current){link.setAttribute('aria-current','page');}
  });
  document.querySelectorAll('a[href="index-new.html"],a[href="index.html"]').forEach(function(link){link.setAttribute('href','/');});

  if(/^(mini|petite|junior|juniorettes|teen)-competition-team\.html$/.test(current)||current==='team-only.html'||current==='competition-auditions.html'){
    document.body.setAttribute('data-competition-team','true');
  }

  if(current==='competition.html'){
    document.querySelectorAll('a[href="teen-competition-team.html"] h3').forEach(function(h){h.textContent='Teen / Senior Competition Team';});
  }

  if(isHome){
    document.title='Dance Classes Near Toledo & Temperance | Stage Starz Academy of Dance';
    var description='Dance classes for ages 3+ in Temperance, Michigan, serving Bedford Township, southern Monroe County and the Toledo area. Recreational and competitive programs at Stage Starz Academy of Dance.';
    var meta=document.querySelector('meta[name="description"]');
    if(meta){meta.setAttribute('content',description);}
    function headMeta(attr,key,value){var selector='meta['+attr+'="'+key+'"]';var el=document.querySelector(selector);if(!el){el=document.createElement('meta');el.setAttribute(attr,key);document.head.appendChild(el);}el.setAttribute('content',value);}
    function headLink(rel,href){var el=document.querySelector('link[rel="'+rel+'"]');if(!el){el=document.createElement('link');el.rel=rel;document.head.appendChild(el);}el.href=href;}
    headLink('canonical','https://www.stagestarzdance.net/');
    headMeta('property','og:type','website');
    headMeta('property','og:site_name','Stage Starz Academy of Dance');
    headMeta('property','og:title','Dance Classes Near Toledo & Temperance | Stage Starz');
    headMeta('property','og:description',description);
    headMeta('property','og:url','https://www.stagestarzdance.net/');
    headMeta('property','og:image','https://www.stagestarzdance.net/assets/images/audriana-homepage-hero.jpg');
    headMeta('name','twitter:card','summary_large_image');
    headMeta('name','twitter:title','Stage Starz Academy of Dance');
    headMeta('name','twitter:description',description);
    headMeta('name','twitter:image','https://www.stagestarzdance.net/assets/images/audriana-homepage-hero.jpg');

    var trust=document.querySelector('.trust-strip');
    if(trust&&!document.querySelector('.ss-local-proof')){
      var local=document.createElement('section');
      local.className='ss-local-proof';
      local.setAttribute('aria-label','Serving local dance families');
      local.innerHTML='<div class="ss-local-proof-inner"><div class="ss-local-proof-copy"><strong>Dance training close to home.</strong><span>Conveniently located in Temperance for families throughout Bedford Township, southern Monroe County and the Toledo area.</span></div><div class="ss-local-proof-item">Temperance, MI<small>6800 Lewis Ave</small></div><div class="ss-local-proof-item">Ages 3+<small>Beginner through advanced</small></div><div class="ss-local-proof-item">Recreational + Competitive<small>A path for every dancer</small></div></div>';
      trust.insertAdjacentElement('afterend',local);
    }

    var finalCta=document.querySelector('.cta');
    if(finalCta&&!document.querySelector('.ss-parent-guide')){
      var guide=document.createElement('section');
      guide.className='ss-parent-guide';
      guide.setAttribute('aria-labelledby','ss-parent-guide-title');
      guide.innerHTML='<div class="ss-parent-guide-inner"><div class="ss-parent-guide-head"><p class="eyebrow">New to Stage Starz?</p><h2 id="ss-parent-guide-title">Starting dance should feel simple.</h2><p>Whether your dancer is brand new or ready for a new challenge, we’ll help you find the right starting point.</p></div><div class="ss-parent-guide-grid"><article><span>01</span><h3>Choose by age & level</h3><p>Browse our clear program pathways for ages 3 through advanced dancers.</p><a href="classes.html">View class options →</a></article><article><span>02</span><h3>Not sure which class?</h3><p>Use the Class Finder to narrow the choices and find a comfortable fit.</p><a href="class-finder.html">Use the Class Finder →</a></article><article><span>03</span><h3>Have a question first?</h3><p>Tell us about your dancer and our studio can help point you in the right direction.</p><a href="contact.html">Ask Stage Starz →</a></article></div><div class="ss-parent-guide-note"><strong>Convenient for Toledo-area families.</strong> Stage Starz is located at 6800 Lewis Ave in Temperance, just north of Toledo, with recreational and competitive opportunities under one studio roof.</div></div>';
      finalCta.insertAdjacentElement('beforebegin',guide);
    }

    if(!document.querySelector('.ss-mobile-cta')){
      var mobile=document.createElement('nav');
      mobile.className='ss-mobile-cta';
      mobile.setAttribute('aria-label','Quick actions');
      mobile.innerHTML='<a class="primary" href="classes.html">Find Classes</a><a class="secondary" href="contact.html">Ask a Question</a>';

      var hero=document.querySelector('.hero');
      var mobileMedia=window.matchMedia('(max-width:640px)');
      function setQuickActionsVisible(show){
        document.body.classList.toggle('ss-past-hero',!!show);
        mobile.style.opacity=show?'1':'0';
        mobile.style.transform=show?'translateY(0)':'translateY(18px)';
        mobile.style.pointerEvents=show?'auto':'none';
        mobile.setAttribute('aria-hidden',show?'false':'true');
      }
      mobile.style.transition='opacity .24s ease, transform .24s ease';
      if(mobileMedia.matches&&hero){
        setQuickActionsVisible(hero.getBoundingClientRect().bottom<=0);
      }else{
        setQuickActionsVisible(true);
      }
      document.body.appendChild(mobile);

      if(mobileMedia.matches&&hero){
        if('IntersectionObserver' in window){
          var quickActionsObserver=new IntersectionObserver(function(entries){
            entries.forEach(function(entry){
              if(entry.target===hero){setQuickActionsVisible(!entry.isIntersecting);}
            });
          },{threshold:0});
          quickActionsObserver.observe(hero);
        }else{
          var updateQuickActions=function(){setQuickActionsVisible(hero.getBoundingClientRect().bottom<=0);};
          window.addEventListener('scroll',updateQuickActions,{passive:true});
          updateQuickActions();
        }
      }
    }
  }

  if(isRegistration){
    var jrCard=document.querySelector('.jackrabbit-card');
    var jrFrame=document.querySelector('.jackrabbit-frame');
    if(jrCard&&jrFrame&&!jrCard.querySelector('.ss-jr-status')){
      var status=document.createElement('div');
      status.className='ss-jr-status';
      status.innerHTML='<strong>Live Class Openings</strong><span>Select the registration option beside the class you want.</span>';
      jrFrame.insertAdjacentElement('beforebegin',status);

      var foot=document.createElement('div');
      foot.className='ss-jr-foot';
      foot.innerHTML='<span>Need help choosing the right class?</span><a href="contact.html">Ask Stage Starz for guidance →</a>';
      jrFrame.insertAdjacentElement('afterend',foot);
    }
  }

  // Only install the legacy fallback video when the managed Website Video player
  // has not already replaced the performance artwork.
  var performanceArt=document.querySelector('.performance-art:not(.ss-home-performance-video)');
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
