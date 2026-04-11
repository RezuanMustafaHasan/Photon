export const fetchTodayRevision = async ({ token }) => {
  const response = await fetch('/api/revision/today', {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  const data = await response.json().catch(() => ({}));
  return { response, data };
};

export const reviewRevisionTask = async ({ token, taskId, outcome }) => {
  const response = await fetch(`/api/revision/${encodeURIComponent(taskId)}/review`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ outcome }),
  });

  const data = await response.json().catch(() => ({}));
  return { response, data };
};
