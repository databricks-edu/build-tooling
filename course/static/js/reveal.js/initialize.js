Reveal.initialize({
  width: 960,
  height: 540,
  center: true,
  controls: true,
  controlsTutorial: false,
  controlsLayout: 'bottom-right',
  progress: false,
  slideNumber: true,
  showSlideNumber: 'speaker',
  hash: true,
  history: true,
  keyboard: true,
  overview: true,
  touch: true,
  fragments: true,
  help: true,
  autoPlayMedia: false,
  transition: 'fade',
  transitionSpeed: 'default',
  parallaxBackgroundSize: '960px 540px',
  autoPlayMedia: true,
  math: {
    mathjax: '$mathjaxurl$',
    config: 'TeX-AMS_HTML-full',
    tex2jax: {
      inlineMath: [['\\(','\\)']],
      displayMath: [['\\[','\\]']],
      balanceBraces: true,
      processEscapes: false,
      processRefs: true,
      processEnvironments: true,
      preview: 'TeX',
      skipTags: ['script','noscript','style','textarea','pre','code'],
      ignoreClass: 'tex2jax_ignore',
      processClass: 'tex2jax_process'
    },
  },
  copycode: {
    copy: "copy",
    copied: "copied",
    timeout: 1000,
    copybg: "#1B3139",
    copiedbg: "#FF3621",
    copycolor: "white",
    copiedcolor: "white"
  },
  highlight: {
    escapeHTML: false,
    dataTrim: true,
    highlightOnLoad: true
  },


  // reveal.js plugins
  plugins: [
    CopyCode,
    RevealMath,
    RevealNotes,
    RevealZoom,
    RevealHighlight
  ]
});
