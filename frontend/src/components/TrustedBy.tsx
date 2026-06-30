import { siteConfig } from '../data/content';

export default function TrustedBy() {
  return (
    <section id="funds" className="scroll-mt-28 relative z-20 py-6 max-w-7xl mx-auto px-6 md:px-12 w-full">
      <div className="glass-panel rounded-xl bg-brand-panel/20 backdrop-blur-md px-6 py-4 flex flex-col lg:flex-row items-center justify-between gap-6 border border-white/5">
        
        {/* Left Side: Muted Label */}
        <div className="text-left shrink-0">
          <p className="text-[9px] uppercase tracking-[0.2em] text-brand-gold/60 font-semibold leading-tight max-w-[150px] text-center lg:text-left">
            {siteConfig.trustedByText}
          </p>
        </div>

        {/* Right Side: Accepted fund categories */}
        <div className="flex flex-wrap items-center justify-center lg:justify-end gap-x-8 gap-y-4 opacity-70">
          {siteConfig.fundCategories.map((category) => (
            <div
              key={category}
              className="font-sans font-semibold text-brand-textPrimary text-xs tracking-wide select-none cursor-default hover:text-brand-goldLight transition-colors duration-300"
            >
              {category}
            </div>
          ))}
          <span className="text-[10px] text-brand-textMuted font-light italic">
            subject to channel availability
          </span>
        </div>

      </div>
    </section>
  );
}
