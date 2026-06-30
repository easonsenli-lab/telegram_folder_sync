import { Shield, Zap, Compass, CheckCircle } from 'lucide-react';
import { siteConfig } from '../data/content';

const icons = [Shield, Zap, Compass, CheckCircle];

export default function CapabilityStrip() {
  return (
    <section id="solutions" className="scroll-mt-28 relative z-30 py-10 px-6 md:px-12 max-w-7xl mx-auto w-full">
      <div className="rounded-2xl grid grid-cols-1 md:grid-cols-4 divide-y md:divide-y-0 md:divide-x divide-brand-gold/20 p-5 md:p-7 bg-[#070A0F]/95 border border-brand-gold/20 shadow-[0_24px_80px_rgba(0,0,0,0.55)] backdrop-blur-xl">
        {siteConfig.capabilities.map((item, idx) => {
          const Icon = icons[idx];
          return (
            <div
              key={item.title}
              className="flex flex-col items-start p-4 md:px-6 transition-all duration-500 hover:bg-brand-gold/8 group relative rounded-lg"
            >
              {/* Linear gold icon */}
              <div className="w-10 h-10 rounded-lg bg-brand-gold/10 border border-brand-gold/35 flex items-center justify-center text-brand-goldLight shadow-[0_0_22px_rgba(217,164,65,0.12)] group-hover:scale-110 group-hover:bg-brand-gold/15 transition-all duration-300 mb-4">
                <Icon className="w-5 h-5" strokeWidth={1.5} />
              </div>
              
              {/* Title */}
              <h4 className="text-xs uppercase tracking-widest text-[#FFF7E8] font-semibold mb-2 group-hover:text-brand-goldLight transition-colors">
                {item.title}
              </h4>
              
              {/* Description */}
              <p className="text-[11px] leading-relaxed text-[#C7C2B8] font-light mb-4 min-h-[40px]">
                {item.description}
              </p>

            </div>
          );
        })}
      </div>
    </section>
  );
}
