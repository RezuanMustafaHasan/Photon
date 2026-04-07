import { useEffect, useMemo, useState } from 'react';
import { formatRateLimitWait, getRateLimitRemainingSeconds } from '../utils/rateLimit.js';

const RateLimitScreen = ({ notice }) => {
  const [now, setNow] = useState(Date.now());

  const remainingSeconds = useMemo(
    () => getRateLimitRemainingSeconds(notice, now),
    [notice, now],
  );

  useEffect(() => {
    if (!notice || remainingSeconds <= 0) {
      return undefined;
    }

    const intervalId = setInterval(() => {
      setNow(Date.now());
    }, 1000);

    return () => {
      clearInterval(intervalId);
    };
  }, [notice, remainingSeconds]);

  return (
    <div className="min-h-screen d-flex align-items-center justify-content-center px-3" style={{ backgroundColor: '#FFF7ED' }}>
      <main className="container" style={{ maxWidth: 560 }}>
        <div className="bg-white border border-red-100 rounded-2xl p-4 p-sm-5 shadow-sm">
          <div className="d-flex align-items-center gap-3 mb-4">
            <div
              className="rounded-3 d-flex align-items-center justify-content-center text-white fw-bold shadow-sm"
              style={{
                width: '2.5rem',
                height: '2.5rem',
                background: 'linear-gradient(to right, #FF4D4D, #FF9F1C)',
              }}
            >
              !
            </div>
            <div>
              <div className="fw-bold text-primary">Rate limit reached</div>
              <div className="text-secondary small">Please wait before trying again</div>
            </div>
          </div>

          <div className="bg-red-50 border border-red-100 rounded-3 p-3 text-red-700 small mb-3">
            {notice?.message || 'Too many requests right now.'}
          </div>

          <div className="bg-orange-50 border border-orange-100 rounded-3 p-3 mb-3">
            <div className="small text-secondary mb-1">Next retry in</div>
            <div className="fw-bold text-primary fs-4">
              {remainingSeconds > 0 ? formatRateLimitWait(remainingSeconds) : 'Now'}
            </div>
          </div>

          {notice?.policy && (
            <div className="text-secondary small">
              Policy: <span className="fw-semibold">{notice.policy}</span>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default RateLimitScreen;
