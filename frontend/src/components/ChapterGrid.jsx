import { useEffect, useState } from 'react';
import ChapterCard from './ChapterCard';

const staticMeta = [
  { status: 'Completed', progress: 100 },
  { progress: 45 },
  { status: 'Weak', progress: 20 },
  { progress: 0 },
  { progress: 0 },
];

const ChapterGrid = ({ onChapterClick }) => {
  const [chapters, setChapters] = useState([]);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');

  useEffect(() => {
    let mounted = true;
    const loadChapters = async () => {
      setStatus('loading');
      setError('');
      try {
        const response = await fetch('/api/chapters');
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.message || 'Failed to load chapters');
        }
        if (mounted) {
          const items = Array.isArray(data.chapters) ? data.chapters : [];
          const mapped = items.map((chapter, index) => {
            const meta = staticMeta[index % staticMeta.length] || {};
            return {
              title: chapter.chapter_name_bn || chapter.chapter_name || 'Untitled',
              status: meta.status,
              progress: meta.progress,
            };
          });
          setChapters(mapped);
          setStatus('ready');
        }
      } catch (err) {
        if (mounted) {
          setError(err.message);
          setStatus('error');
        }
      }
    };
    loadChapters();
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <div className="mt-5">
      <h2 className="fs-5 fw-bold text-primary mb-4 d-flex align-items-center gap-2">
        📘 HSC Physics Chapters
      </h2>
      {status === 'error' && <div className="text-danger mb-3">{error}</div>}
      <div className="row row-cols-1 row-cols-sm-2 row-cols-lg-4 row-cols-xl-5 g-4">
        {chapters.map((chapter, index) => (
          <div key={index} className="col">
            <ChapterCard {...chapter} onClick={() => onChapterClick(chapter.title)} />
          </div>
        ))}
      </div>
    </div>
  );
};

export default ChapterGrid;
