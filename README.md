# Budgetika

**Intelligent Personal Finance Management Platform**

Budgetika is a comprehensive, full-stack fintech application designed to empower individuals with intelligent insights into their financial habits. Built with a modern, decoupled architecture, it seamlessly blends robust financial tracking with advanced AI-driven automation.

## 🚀 Features

Budgetika provides a complete suite of tools for personal finance management:

* **Multi-Wallet Architecture:** Manage multiple accounts (e.g., checking, savings) with independent balances, currencies, and transaction histories.
* **Intelligent Categorization:** Leverage OpenAI's GPT models to automatically categorize transactions and import data from CSV files based on learned merchant patterns.
* **Recurring Transactions:** Automate daily, weekly, monthly, or yearly financial events (e.g., rent, subscriptions) with built-in catch-up logic for missed occurrences.
* **Smart Budgeting:** Set per-category spending caps, define custom monthly overrides, and receive real-time alerts when limits are breached.
* **Goal Tracking:** Define and monitor savings goals with automated progress calculation based on projected monthly savings rates.
* **Cross-Currency Support:** Perform real-time currency conversion using the Frankfurter API, enabling seamless management of international assets.
* **Comprehensive Analytics:** Visualize spending trends through interactive charts, category breakdowns, and month-over-month comparisons.
* **Data Portability:** Import transactions via CSV with AI-assisted mapping, and export your entire financial history for external analysis.

## 🏗️ Architecture

Budgetika utilizes a modern, service-oriented architecture separating the API layer from the presentation layer:

| Layer | Technology Stack | Description |
| :--- | :--- | :--- |
| **Frontend** | Next.js 15, React 19, TypeScript | High-performance, server-side rendered UI utilizing TanStack Query for state management and Tailwind CSS for styling. |
| **Backend API** | Django 5.1, Django REST Framework | Robust, secure RESTful API handling business logic, authentication (JWT), and data persistence. |
| **Database** | SQLite (Dev) / PostgreSQL (Prod) | Relational database storing all financial records, user data, and AI usage metrics. |
| **AI Integration** | OpenAI API | Server-side integration for transaction categorization and receipt scanning capabilities. |

## 🛠️ Getting Started

### Prerequisites

* Python 3.13+
* Node.js 18+
* pnpm (recommended) or npm

### Backend Setup

1. Navigate to the backend directory and set up the virtual environment:
   ```bash
   cd backend
   python3.13 -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies and initialize the database:
   ```bash
   pip install -r requirements.txt
   cp .env.example .env
   python manage.py migrate
   python manage.py createsuperuser
   python manage.py seed_categories
   ```

3. Start the Django development server:
   ```bash
   python manage.py runserver 8100
   ```

### Frontend Setup

1. Navigate to the frontend directory and install dependencies:
   ```bash
   cd frontend
   pnpm install
   ```

2. Configure the environment and start the development server:
   ```bash
   cp .env.example .env.local
   pnpm dev
   ```

The application will be available at `http://localhost:3100`.

## 📦 Self-Hosting & Deployment

Budgetika is designed for easy self-hosting on personal servers or mini-PCs for complete data sovereignty. 

* **Configuration:** All sensitive keys and database connections are managed via `.env` files using `django-environ`.
* **Deployment:** The application is lightweight and can be deployed using Gunicorn for the backend and standard Next.js production builds for the frontend.
* **Backup Strategy:** Automated daily backups can be configured using the provided shell scripts and `launchd`/`cron` schedules.

For detailed instructions on deploying to a local network or production environment, refer to the `RUNBOOK.md`.

## 🤝 Contributing

We welcome contributions! Please read our `CONTRIBUTING.md` (if available) or open an issue to discuss proposed changes. Ensure all new features include corresponding unit tests in the `backend/tests/` directory.

## 📄 License

This project is licensed under the MIT License - see the `LICENSE` file for details.
