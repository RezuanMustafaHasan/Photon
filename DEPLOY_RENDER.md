# Deploy Photon on Render

This repo deploys as five Render services:

- `FastAPI`: Python Web Service used internally by the Node backend for chat and exams.
- `backend`: Node Web Service for the student app API.
- `frontend`: Vite Static Site for students.
- `admin-backend`: Node Web Service for admin APIs.
- `admin-frontend`: Vite Static Site for admins.

## 1. Before You Start

1. Push this repo to GitHub, GitLab, or Bitbucket.
2. Create a MongoDB Atlas database and copy the connection string.
3. Generate three different secrets:

   ```bash
   openssl rand -base64 48
   ```

   Generate one value each for `JWT_SECRET`, `ADMIN_JWT_SECRET`, and `FASTAPI_INTERNAL_API_KEY`.

4. Keep `.env` files local only. Use Render's Environment tab for production values.

## 2. FastAPI Service

1. Go to the Render dashboard.
2. Click **New** > **Web Service**.
3. Connect your repo.
4. Set:
   - **Name**: `photon-fastapi`
   - **Root Directory**: `FastAPI`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables:
   - `ENVIRONMENT=production`
   - `MONGODB_URI=<your MongoDB Atlas URI>`
   - `FASTAPI_INTERNAL_API_KEY=<same value you will use in backend>`
   - `GROQ_API_KEY=<your Groq API key>`
   - `CHAT_TIMING_LOGS=false`
6. Click **Deploy Web Service**.
7. Copy the live URL, for example `https://photon-fastapi.onrender.com`.

## 3. Student Backend Service

1. Click **New** > **Web Service**.
2. Connect the same repo.
3. Set:
   - **Name**: `photon-backend`
   - **Root Directory**: `backend`
   - **Runtime**: `Node`
   - **Build Command**: `npm ci`
   - **Start Command**: `npm start`
4. Add environment variables:
   - `NODE_ENV=production`
   - `MONGODB_URI=<same MongoDB Atlas URI>`
   - `JWT_SECRET=<new random secret>`
   - `FASTAPI_BASE_URL=<FastAPI URL from step 2>`
   - `FASTAPI_INTERNAL_API_KEY=<same value used in FastAPI>`
   - `CORS_ORIGINS=https://photon-frontend.onrender.com`
   - `TRUST_PROXY=1`
   - Optional but recommended: `RATE_LIMIT_ENABLED=true`
   - Optional with rate limiting: `UPSTASH_REDIS_URL=<rediss:// Upstash URL>`
5. Click **Deploy Web Service**.
6. Copy the live URL, for example `https://photon-backend.onrender.com`.

## 4. Student Frontend Static Site

1. Click **New** > **Static Site**.
2. Connect the same repo.
3. Set:
   - **Name**: `photon-frontend`
   - **Root Directory**: `frontend`
   - **Build Command**: `npm ci && npm run build`
   - **Publish Directory**: `dist`
4. Add redirect/rewrite rules in this order:
   - **Rewrite** `/api/*` to `https://photon-backend.onrender.com/api/*`
   - **Rewrite** `/*` to `/index.html`
5. Click **Deploy Static Site**.
6. If Render gives the frontend a different URL than expected, update `CORS_ORIGINS` on `photon-backend` and redeploy the backend.

## 5. Admin Backend Service

1. Click **New** > **Web Service**.
2. Connect the same repo.
3. Set:
   - **Name**: `photon-admin-backend`
   - **Root Directory**: `admin-backend`
   - **Runtime**: `Node`
   - **Build Command**: `npm ci`
   - **Start Command**: `npm start`
4. Add environment variables:
   - `NODE_ENV=production`
   - `MONGODB_URI=<same MongoDB Atlas URI>`
   - `ADMIN_JWT_SECRET=<new random secret>`
   - `ADMIN_EMAIL=<your admin email>`
   - `ADMIN_PASSWORD=<strong admin password>`
   - `ADMIN_NAME=Photon Admin`
   - `ADMIN_ROLE=admin`
   - `ADMIN_CORS_ORIGINS=https://photon-admin-frontend.onrender.com`
   - `TRUST_PROXY=1`
   - Optional for image uploads: `CLOUDINARY_CLOUD_NAME`
   - Optional for image uploads: `CLOUDINARY_API_KEY`
   - Optional for image uploads: `CLOUDINARY_API_SECRET`
5. Click **Deploy Web Service**.
6. Copy the live URL, for example `https://photon-admin-backend.onrender.com`.

## 6. Admin Frontend Static Site

1. Click **New** > **Static Site**.
2. Connect the same repo.
3. Set:
   - **Name**: `photon-admin-frontend`
   - **Root Directory**: `admin-frontend`
   - **Build Command**: `npm ci && npm run build`
   - **Publish Directory**: `dist`
4. Add environment variable:
   - `VITE_ADMIN_API_URL=https://photon-admin-backend.onrender.com`
5. Add redirect/rewrite rule:
   - **Rewrite** `/*` to `/index.html`
6. Click **Deploy Static Site**.
7. If Render gives the admin frontend a different URL than expected, update `ADMIN_CORS_ORIGINS` on `photon-admin-backend` and redeploy the admin backend.

## 7. Final Checks

1. Open the student frontend URL.
2. Sign up and log in.
3. Open a lesson and send one chat message.
4. Generate one exam.
5. Open the admin frontend URL.
6. Log in with your admin account.
7. Check Render logs for all services. There should be no missing environment variable errors and no `401` errors between the backend and FastAPI.

## Security Notes

- Do not deploy with local `.env` values.
- Do not reuse `JWT_SECRET`, `ADMIN_JWT_SECRET`, and `FASTAPI_INTERNAL_API_KEY`.
- `FASTAPI_INTERNAL_API_KEY` must match in `backend` and `FastAPI`.
- Do not add `OPENAI_API_KEY` on Render. The app is intentionally locked to Groq for demo-cost safety.
- Use `rediss://`, not `redis://`, for Upstash Redis.
- If a frontend URL changes, update the matching CORS env var and redeploy the API service.
