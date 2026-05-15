# Photon

Photon is an AI-powered HSC Physics learning platform built for Bangladeshi students. It combines lesson-aware tutoring, adaptive exam generation, mastery tracking, spaced revision, and an admin content-management workflow into one full-stack application.

The project is designed as a real product prototype rather than a simple chatbot demo. Students can study chapter by chapter, ask grounded questions from lesson content, generate practice exams, receive weakness summaries, and get revision tasks based on their actual learning signals.

## Screenshots

Place screenshots in a folder named `docs/screenshots/` and replace the placeholder files below. The titles are written as a capture checklist so the project reads clearly during interviews.

### 1. Landing and Authentication

![Landing page showing Photon branding and student entry point](docs/screenshots/01-landing-page.png)

Capture the first screen a recruiter sees: Photon branding, the learning promise, and the sign-in/sign-up entry point.

![Student login page](docs/screenshots/02-student-login.png)

Capture the student authentication flow.

### 2. Student Dashboard

![Student dashboard with mastery progress and study suggestions](docs/screenshots/03-dashboard-overview.png)

Capture the main dashboard with overall progress, chapter cards, weak lesson suggestions, and revision prompts visible.

![Chapter grid showing progress states](docs/screenshots/04-chapter-grid-progress.png)

Capture chapter cards showing states such as `Open Chapter`, `Focus Now`, and `Revisit`.

### 3. Lesson Chat and AI Tutoring

![Lesson chat with sidebar and selected HSC Physics lesson](docs/screenshots/05-lesson-chat-layout.png)

Capture the lesson study screen with the lesson sidebar, selected lesson, model selector, and chat area.

![AI tutor explaining a concept with equations](docs/screenshots/06-ai-tutor-explanation.png)

Capture a strong AI response with markdown structure and physics formulas rendered cleanly.

![Lesson-flow check question after AI teaching](docs/screenshots/07-lesson-flow-check-question.png)

Capture the guided learning flow where the tutor teaches one concept and asks a focused check question.

![AI response with textbook citation or source reference](docs/screenshots/08-grounded-response-citation.png)

Capture a response that shows the answer is grounded in lesson content, preferably with citation/source metadata visible.

### 4. Exams and Weakness Analysis

![Exam setup page with chapter and topic selection](docs/screenshots/09-exam-topic-selection.png)

Capture the exam setup flow where students select chapters, topics, question count, and the Groq model.

![Generated MCQ exam interface](docs/screenshots/10-generated-exam.png)

Capture the active exam UI with multiple-choice questions and answer options.

![Exam result summary with score and weak topic suggestions](docs/screenshots/11-exam-result-analysis.png)

Capture the completed exam result, score, wrong answers, and AI-generated study advice.

![Previous exam history page](docs/screenshots/12-exam-history.png)

Capture saved exam attempts so recruiters can see persistence and review flow.

### 5. Revision and Mastery

![Revision queue generated from mastery signals](docs/screenshots/13-revision-queue.png)

Capture the daily revision card or revision task list showing due lessons.

![Mastery detail showing weak lessons and progress](docs/screenshots/14-mastery-signals.png)

Capture any dashboard section that shows mastery scores, weak lessons, or study recommendations.

### 6. Admin Workflow

![Admin dashboard for managing lesson content](docs/screenshots/15-admin-dashboard.png)

Capture the admin interface after login.

![Admin content editor or JSON upload workflow](docs/screenshots/16-admin-content-management.png)

Capture content upload/editing for textbook JSON.

![Admin lesson image upload with Cloudinary-backed media](docs/screenshots/17-admin-image-management.png)

Capture image upload or image management for lesson visuals.

### 7. Deployment

![Render services dashboard for Photon deployment](docs/screenshots/18-render-services.png)

Capture the Render dashboard showing the deployed frontend, backend, FastAPI, admin frontend, and admin backend services.

## Why This Project Exists

HSC Physics students often struggle with three connected problems:

- They need explanations that follow their textbook and syllabus, not generic AI answers.
- They need practice questions that target weak topics instead of random revision.
- They need a clear way to know what to study next.

Photon solves this by combining structured textbook content with AI tutoring and a mastery model. The app tracks lesson activity, chat confusion signals, exam performance, and revision outcomes to build a practical learning loop.

## Core Features

- **AI lesson tutor**: Students can open a chapter and lesson, then ask questions in a chat interface.
- **Lesson-flow teaching mode**: The tutor can teach a lesson one concept at a time and ask small checks before moving forward.
- **Grounded explanations**: AI responses are anchored to stored lesson content and can include citations/source lesson references.
- **Groq-only AI deployment mode**: The public demo is locked to Groq models to avoid accidental OpenAI quota burn.
- **Exam generator**: Students can select chapters/topics and generate MCQ-style practice exams.
- **Exam analysis**: Completed exams are saved with score, wrong answers, topic weaknesses, and AI study suggestions.
- **Mastery tracking**: The backend computes lesson and chapter mastery from activity, completion, confusion, and exam performance.
- **Revision queue**: Weak or recently missed lessons are scheduled for review using simple spaced-repetition behavior.
- **Student auth**: Users can sign up, log in, and keep their study history.
- **Admin dashboard**: Admin/editor users can manage textbook content and lesson images.
- **Image support**: Lesson images can be uploaded through the admin backend and served from Cloudinary.
- **Production deployment guide**: The repo includes a Render deployment checklist in [DEPLOY_RENDER.md](./DEPLOY_RENDER.md).

## Tech Stack

### Frontend

| Area | Technology | Why it is used |
| --- | --- | --- |
| Student UI | React 19 + Vite | Fast local development, component-based UI, and simple static deployment. |
| Routing | React Router | Dashboard, auth, study flow, exam, and chapter pages are handled client-side. |
| Styling | Bootstrap + custom CSS | Quick responsive layout with custom product styling where needed. |
| Rich text | react-markdown, remark-gfm, remark-math, rehype-katex, KaTeX | AI explanations can include markdown, lists, citations, and physics formulas. |

### Student Backend

| Area | Technology | Why it is used |
| --- | --- | --- |
| API server | Node.js + Express | Simple REST API for auth, chapters, chat proxying, exams, mastery, and revision. |
| Database ODM | Mongoose | Structured models for users, exams, mastery records, and revision tasks. |
| Auth | JWT + bcryptjs | Stateless student sessions and secure password hashing. |
| Rate limiting | express-rate-limit + optional Redis/Upstash | Protects auth, chat, exam generation, and API endpoints from demo abuse. |
| Security headers | Helmet | Adds baseline HTTP security headers for production. |

### AI Service

| Area | Technology | Why it is used |
| --- | --- | --- |
| AI API | FastAPI | Keeps Python AI orchestration separate from the Node API. |
| LLM provider | Groq via LangChain | Fast hosted inference for public demo use without exposing OpenAI billing. |
| Workflow logic | LangGraph/LangChain Core | Structures lesson-flow, grounded chat, exam generation, and parsing steps. |
| Data access | PyMongo | Reads lesson content and stores chat history/state in MongoDB. |

### Admin System

| Area | Technology | Why it is used |
| --- | --- | --- |
| Admin frontend | React + Vite | Lightweight admin interface for content operations. |
| Admin backend | Express | Separate service boundary for admin-only APIs. |
| File uploads | Multer | Handles JSON and image upload workflows. |
| Media hosting | Cloudinary | Stores lesson images outside the app server. |
| Admin auth | JWT | Role-aware admin/editor access. |

### Infrastructure

| Area | Technology | Why it is used |
| --- | --- | --- |
| Database | MongoDB Atlas | Shared persistence for users, lessons, exams, chat state, and mastery data. |
| Redis | Upstash Redis, optional | Distributed rate-limit store for production deployments. |
| Hosting | Render | Simple deployment for static sites and web services. |

## Architecture

Photon is split into five deployable services:

```text
Student Browser
  |
  | React/Vite static site
  v
Student Backend (Express)
  |       |        |        |
  |       |        |        +--> MongoDB: users, exams, mastery, revision
  |       |        +----------> Redis/Upstash: rate limiting
  |       +-------------------> FastAPI AI service
  |                              |
  |                              +--> Groq LLM
  |                              +--> MongoDB: lesson content, chat state
  |
Admin Browser
  |
  v
Admin Frontend (React/Vite)
  |
  v
Admin Backend (Express)
  |
  +--> MongoDB: textbook/content documents
  +--> Cloudinary: lesson images
```

This separation keeps the AI orchestration isolated from the main student API. It also makes deployment easier: the student frontend, admin frontend, Node APIs, and FastAPI service can scale or restart independently.

## Learning Flow

1. A student signs up or logs in.
2. The dashboard shows chapter progress, weak lessons, and revision suggestions.
3. The student opens a chapter and selects a lesson.
4. The chat sends chapter, lesson, user message, and model choice to the Node backend.
5. The Node backend authenticates the user, rate-limits the request, and forwards it to FastAPI.
6. FastAPI loads lesson content from MongoDB, builds the tutoring prompt, calls Groq, validates JSON output, and returns a structured response.
7. The frontend renders markdown, math, images, source references, and the next check question.
8. Lesson activity, confusion signals, and completion events update the mastery model.
9. Exams and revision tasks feed back into the same mastery loop.

## Mastery and Revision Model

Photon does not treat progress as a simple "visited page" flag. It combines multiple signals:

- Time spent on a lesson
- Whether a lesson was completed in the guided flow
- Chat messages that indicate confusion
- Correct and wrong exam answers per lesson/topic
- Recent activity and revision outcomes

The backend converts these into a lesson mastery score and chapter-level progress. Weak lessons are then surfaced in the dashboard and revision queue.

## Security and Demo-Safety Decisions

This project includes production-minded safeguards because it is meant to be deployed publicly for interviews:

- JWT auth for student and admin flows
- Password hashing with bcrypt
- Helmet security headers
- CORS allowlists for deployed frontend URLs
- Rate limiting for auth, chat, exam generation, and API routes
- Optional Redis-backed rate limiting for multi-instance deployment
- FastAPI protected by a shared internal API key between Node and Python services
- Groq-only public model access to prevent OpenAI quota abuse
- Local `.env` files ignored by Git

For public demos, do **not** add `OPENAI_API_KEY` to Render. The current app is intentionally configured to use Groq only.

## Repository Structure

```text
.
├── frontend/          # Student React app
├── backend/           # Student Express API
├── FastAPI/           # Python AI service
├── admin-frontend/    # Admin React app
├── admin-backend/     # Admin Express API
├── DEPLOY_RENDER.md   # Render deployment guide
└── Makefile           # Local multi-service runner
```

## Local Development

### Prerequisites

- Node.js
- Python 3.11+
- MongoDB connection string
- Groq API key
- Optional: Upstash Redis for production-like rate limiting
- Optional: Cloudinary account for admin image uploads

### Environment Files

Create local env files from the examples:

```bash
cp backend/.env.example backend/.env
cp FastAPI/.env.example FastAPI/.env
cp admin-backend/.env.example admin-backend/.env
cp frontend/.env.example frontend/.env
cp admin-frontend/.env.example admin-frontend/.env
```

At minimum, set:

```env
MONGODB_URI=your_mongodb_connection_string
GROQ_API_KEY=your_groq_key
JWT_SECRET=your_student_jwt_secret
ADMIN_JWT_SECRET=your_admin_jwt_secret
FASTAPI_INTERNAL_API_KEY=same_value_in_backend_and_fastapi
```

### Install Dependencies

```bash
cd backend && npm install
cd ../frontend && npm install
cd ../admin-backend && npm install
cd ../admin-frontend && npm install
cd ../FastAPI && pip install -r requirements.txt
```

### Run All Services

From the repo root:

```bash
make run
```

Default local URLs:

- Student app: `http://127.0.0.1:5173`
- Admin app: `http://127.0.0.1:5174/admin`
- Student API: `http://127.0.0.1:5001` if `PORT=5001`
- FastAPI service: `http://127.0.0.1:8000`

To stop everything:

```bash
make stop
```

## Testing and Verification

Backend tests:

```bash
cd backend
npm test
```

Frontend build:

```bash
cd frontend
npm run build
```

FastAPI syntax check:

```bash
cd FastAPI
python -m compileall main.py graph tests
```

## Deployment

The deployment target is Render. The app is deployed as:

- `photon-frontend`: static site
- `photon-backend`: Node web service
- `photon-fastapi`: Python web service
- `photon-admin-frontend`: static site
- `photon-admin-backend`: Node web service

Follow the full guide in [DEPLOY_RENDER.md](./DEPLOY_RENDER.md).

## What This Project Demonstrates

Photon demonstrates:

- Full-stack product thinking, not just isolated features
- Multi-service architecture with clear service boundaries
- Practical AI integration with structured outputs, retries, and content grounding
- Authentication, rate limiting, and deployment security
- Data modeling for learning progress and spaced revision
- Admin tooling for managing lesson content and images
- Production deployment planning on Render

## Future Improvements

- Add automated FastAPI tests in CI
- Add streaming AI responses for a more natural chat experience
- Add teacher/admin analytics dashboards
- Add per-user usage quotas for public demos
- Add better observability around LLM latency and parse failures
- Add Docker Compose for one-command local infrastructure

## Author

Built by Rezuan Mustafa Hasan as a full-stack AI learning platform and interview portfolio project.
