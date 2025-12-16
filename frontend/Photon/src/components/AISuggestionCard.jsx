import React from 'react';

const AISuggestionCard = () => {
  return (
    <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 h-full flex flex-col justify-between hover:shadow-md transition-shadow">
      <div>
        <h3 className="text-lg font-bold text-primary mb-4 flex items-center gap-2">
          📌 Next Step for You
        </h3>
        <div className="space-y-3 text-base text-secondary font-bangla leading-relaxed">
          <p>
            You were studying <span className="font-semibold text-primary">"মহাকর্ষ ও অভিকর্ষ"</span> — চলুন সেখান থেকেই শুরু করি।
          </p>
          <p>
            আপনাকে <span className="font-semibold text-primary">"ভেক্টর"</span> অধ্যায়টি revise করা দরকার।
          </p>
          <p className="font-medium text-primary bg-orange-50 p-2 rounded-lg border border-orange-100">
            🎯 Ready? আপনি একটি কলেজ ভর্তি Mock Test দিতে পারেন।
          </p>
        </div>
      </div>
      
      <div className="mt-6">
        <button className="w-full sm:w-auto bg-gradient-to-r from-cta-start to-cta-end text-white px-6 py-2.5 rounded-xl font-semibold shadow-lg shadow-orange-200 hover:shadow-orange-300 hover:-translate-y-0.5 transition-all duration-200 flex items-center justify-center gap-2">
          Start Revision
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z" clipRule="evenodd" />
          </svg>
        </button>
      </div>
    </div>
  );
};

export default AISuggestionCard;
