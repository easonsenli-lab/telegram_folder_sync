import { siteConfig } from '../data/content';
import EarthNetwork from './EarthNetwork';
import MetricsPanel from './MetricsPanel';

export default function HeroSection() {
  return (
    <section id="top" className="scroll-mt-28 relative min-h-screen w-full flex items-center justify-between overflow-hidden pt-20 px-6 md:px-12 max-w-[1400px] mx-auto z-10 select-none">
      
      {/* 1. Earth background */}
      <EarthNetwork />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center w-full min-h-[calc(100vh-80px)]">
        
        {/* 2. Left Column: Text Copy Area (30% space) */}
        <div className="lg:col-span-5 flex flex-col items-start text-left z-10 pt-10 lg:pt-0">
          
          {/* Headline (Thin elegant Serif style) */}
          <h1 className="text-4xl sm:text-5xl lg:text-[3.25rem] font-light tracking-tight leading-[1.08] text-brand-textPrimary font-serif mb-6">
            {siteConfig.hero.titleLines[0]}<br />
            <span className="text-gold-gradient font-light italic">{siteConfig.hero.titleLines[1]}</span><br />
            {siteConfig.hero.titleLines[2]}
          </h1>

          {/* Subheadline */}
          <p className="text-xs sm:text-sm text-brand-textSecondary max-w-sm font-sans font-light leading-relaxed mb-8">
            {siteConfig.hero.subtitle}
          </p>

          {/* CTAs - Explore Our Network Button with Arrow (1-to-1 Detail) */}
          <div className="flex flex-wrap gap-4 w-full sm:w-auto">
            <a
              href="#solutions"
              className="group flex items-center gap-3 px-6 py-3 rounded-full text-xs font-light tracking-widest text-brand-textPrimary border border-brand-gold/45 hover:border-brand-gold bg-brand-panel/20 backdrop-blur-sm transition-all duration-300 shadow-lg shadow-brand-gold/5 active:scale-95"
            >
              <span>{siteConfig.hero.primaryBtn.toUpperCase()}</span>
              <span className="w-5 h-5 rounded-full bg-brand-gold/10 border border-brand-gold/30 flex items-center justify-center text-brand-gold group-hover:bg-brand-gold group-hover:text-brand-dark transition-all duration-300 font-sans text-xs">
                →
              </span>
            </a>
          </div>
        </div>

        {/* Space spacer preserving the map as the center visual area. */}
        <div className="lg:col-span-4 h-full pointer-events-none"></div>

        {/* 3. Right Column: Metrics (20% space) */}
        <div className="lg:col-span-3 flex flex-col items-end h-full z-20 py-12 self-stretch">
          
          {/* Top-Right Metrics Panel */}
          <div className="w-full flex justify-end">
            <MetricsPanel />
          </div>
          
        </div>

      </div>

      {/* 4. Bottom-Center mouse scroll indicator (1-to-1 Detail) */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 select-none z-20 animate-pulse-slow">
        <div className="w-5 h-8 rounded-full border border-white/20 flex justify-center p-1 relative">
          <div className="w-1 h-1.5 bg-brand-gold rounded-full animate-[wheel_1.8s_ease-in-out_infinite]"></div>
        </div>
        <span className="text-[8px] uppercase tracking-[0.25em] text-brand-textMuted font-semibold">
          Scroll to Discover
        </span>
      </div>

      <style>{`
        @keyframes wheel {
          0% {
            transform: translateY(0);
            opacity: 0;
          }
          30% {
            opacity: 1;
          }
          80% {
            transform: translateY(6px);
            opacity: 0;
          }
          100% {
            transform: translateY(0);
            opacity: 0;
          }
        }
      `}</style>
    </section>
  );
}
