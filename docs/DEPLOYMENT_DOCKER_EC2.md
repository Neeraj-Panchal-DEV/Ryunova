# Deployment — redirect

**Production runbook (EC2, ALB, GitHub Actions, Docker Compose, secrets, bootstrap):**  
→ **[DEPLOYMENT_EC2_ALB.md](DEPLOYMENT_EC2_ALB.md)**

This file previously described an aspirational multi-container layout (nginx, Celery workers, Redis). The **shipping** stack is **`api` + `web`** only — see **`docker-compose.app-only.yml`** and the linked document.
