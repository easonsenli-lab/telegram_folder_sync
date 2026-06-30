import { siteConfig } from '../data/content';

export default function MissionSection() {
  return (
    <section className="relative z-20 px-6 md:px-12 max-w-7xl mx-auto w-full border-t border-white/5 bg-brand-dark">
      <div className="grid gap-16 py-20">
        <div id="risk" className="scroll-mt-28 grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          <div className="lg:col-span-4">
            <h4 className="text-[10px] uppercase tracking-[0.24em] text-brand-gold/70 font-semibold leading-tight">
              Risk & Operations
            </h4>
          </div>
          <div className="lg:col-span-8 space-y-4">
            <p className="text-[12px] text-brand-textSecondary font-light leading-relaxed max-w-xl">
              {siteConfig.risk.title}
            </p>
            <ul className="grid gap-2 text-[11px] text-brand-textSecondary font-light leading-relaxed">
              {siteConfig.risk.points.map((point) => (
                <li key={point} className="flex gap-2">
                  <span className="mt-1.5 h-1 w-1 rounded-full bg-brand-gold shrink-0" />
                  <span>{point}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div id="flow" className="scroll-mt-28 grid grid-cols-1 lg:grid-cols-12 gap-8 items-start border-t border-white/5 pt-16">
          <div className="lg:col-span-4">
            <h4 className="text-[10px] uppercase tracking-[0.24em] text-brand-gold/70 font-semibold leading-tight">
              Flow
            </h4>
          </div>
          <div className="lg:col-span-8 space-y-4">
            <p className="text-[12px] text-brand-textSecondary font-light leading-relaxed">
              {siteConfig.flow.title}
            </p>
            <div className="grid sm:grid-cols-2 gap-2">
              {siteConfig.flow.steps.map((step, index) => (
                <div key={step} className="border border-brand-gold/15 bg-brand-panel/25 rounded-lg px-3 py-2">
                  <span className="block text-[9px] text-brand-goldLight font-semibold tracking-widest">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <span className="text-[11px] text-brand-textPrimary">{step}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div id="about" className="scroll-mt-28 grid grid-cols-1 lg:grid-cols-12 gap-8 items-start border-t border-white/5 pt-16">
          <div className="lg:col-span-4 flex items-start gap-3">
            <span className="text-brand-gold text-7xl font-serif leading-none select-none opacity-50">
              “
            </span>
          </div>
          <div className="lg:col-span-8 space-y-4">
            <h2 className="text-xl sm:text-2xl font-light text-brand-textPrimary font-sans leading-relaxed select-none">
              <span className="text-gold-gradient font-serif italic font-normal">
                {siteConfig.about.title}
              </span>
            </h2>
            <p className="text-sm text-brand-textSecondary font-light leading-relaxed max-w-xl">
              {siteConfig.about.body}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
