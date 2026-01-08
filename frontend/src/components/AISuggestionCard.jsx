import React from 'react';

const AISuggestionCard = () => {
  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 h-100 d-flex flex-column justify-content-between card-hover-effect">
      <div>
        <h3 className="text-lg-custom fw-bold text-primary mb-4 d-flex align-items-center gap-2">
          📌 Next Step for You
        </h3>
        <div className="vstack gap-3 text-secondary font-bangla leading-relaxed">
          <p>
            You were studying <span className="fw-semibold text-primary">"মহাকর্ষ ও অভিকর্ষ"</span> — চলুন সেখান থেকেই শুরু করি।
          </p>
          <p>
            আপনাকে <span className="fw-semibold text-primary">"ভেক্টর"</span> অধ্যায়টি revise করা দরকার।
          </p>
          <p className="fw-medium text-primary bg-orange-50 p-2 rounded-3 border border-orange-100">
            🎯 Ready? আপনি একটি কলেজ ভর্তি Mock Test দিতে পারেন।
          </p>
        </div>
      </div>
      
      <div className="mt-4">
        <button className="w-100 w-sm-auto custom-gradient-btn text-white px-4 py-2 rounded-xl fw-semibold d-flex align-items-center justify-content-center gap-2">
          Start Revision
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" style={{ width: '1.25rem', height: '1.25rem' }}>
            <path fillRule="evenodd" d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z" clipRule="evenodd" />
          </svg>
        </button>
      </div>
    </div>
  );
};

export default AISuggestionCard;
