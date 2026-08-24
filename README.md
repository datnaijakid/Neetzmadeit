# Neetzmadeit ꧂

An elegant, boutique e-commerce web platform for **Neetzmadeit** — showcasing handmade pieces, custom crochet & knit orders, accessories, and artistic creations.

---

## ✨ Features

- **🛍️ Product Showcase & Shop:**
  - Dynamic product catalog with image galleries and detailed views.
  - Related product recommendations and featured seasonal collections (e.g. *Cozy Fall Collection*).
  - Modal instructions for *"How to Order"*.

- **୨ৎ Custom Order System:**
  - Dedicated custom order portal with multi-channel contact methods (Email, Phone, Instagram, TikTok).
  - Inspiration photo upload support with automatic server-side storage and notifications.

- **🛒 Cart & Checkout:**
  - Session-based shopping cart with quantity adjustments and real-time total calculation.
  - Streamlined checkout delivering itemized order receipts to the business via **Web3Forms**.

- **🔒 Admin Management Dashboard:**
  - Secure authentication (`/login`, `/admin`).
  - Full CRUD operations for products (add multiple images, edit details, toggle featured status, delete).
  - Site settings management for YouTube channel integration and preview videos.

- **🎨 Aesthetic Design:**
  - Warm, cozy autumn color palette with custom typography (*Cormorant Garamond*).
  - Animated announcement ticker for local deliveries.
  - Fully responsive across desktop, tablet, and mobile devices.

---

## 🛠️ Technology Stack

- **Backend:** Python 3, [Flask](https://flask.palletsprojects.com/)
- **Templating & UI:** Jinja2, [Bootstrap 5](https://getbootstrap.com/), Vanilla CSS, FontAwesome
- **Database:** Dual-engine architecture:
  - **Production:** [Neon PostgreSQL](https://neon.tech/) (Serverless Postgres)
  - **Local Development:** SQLite (`neetzmadeit.db` fallback)
- **Form & Email Dispatch:** [Web3Forms API](https://web3forms.com/)
- **Deployment:** [Vercel](https://vercel.com/) via `@vercel/python` serverless runtime

---

## 🚀 Getting Started

### 1. Clone the Repository
```bash
git clone https://github.com/datnaijakid/Neetzmadeit.git
cd Neetzmadeit
```

### 2. Set Up Virtual Environment & Dependencies
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On macOS/Linux:
source .venv/bin/activate

# Install required packages
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file in the root directory (refer to `.env.example`):
```env
# Web3Forms Access Key (https://web3forms.com/)
WEB3FORMS_ACCESS_KEY=your_web3forms_access_key_here

# Neon PostgreSQL Connection URL (https://neon.tech/)
# (Leave blank to use local SQLite neetzmadeit.db)
DATABASE_URL=postgresql://username:password@ep-xxxx-pooler.region.aws.neon.tech/neondb?sslmode=require
```

### 4. (Optional) Migrate Local SQLite to Neon PostgreSQL
If you have data in `neetzmadeit.db` that you wish to transfer to Neon:
```bash
python migrate_to_neon.py
```

### 5. Run the Application Locally
```bash
python main.py
```
Open [http://localhost:5000](http://localhost:5000) in your browser.

---

## ☁️ Deployment on Vercel

1. Push your code to GitHub:
   ```bash
   git add .
   git commit -m "Deploy update"
   git push origin main
   ```
2. Import the project into [Vercel](https://vercel.com/).
3. Add your **Environment Variables** in Vercel Project Settings:
   - `WEB3FORMS_ACCESS_KEY`
   - `DATABASE_URL`
4. Click **Deploy**. Vercel will automatically build and serve the application using `vercel.json`.

---

## 📁 Project Structure

```text
Neetzmadeit/
├── instance/               # Local instance data
├── static/
│   ├── assets/img/         # Product images & brand assets
│   │   └── custom_orders/  # Uploaded inspiration photos
│   └── css/
│       └── styles.css      # Custom styles & design system
├── templates/
│   ├── admin/              # Admin dashboard & product CRUD templates
│   ├── base.html           # Main layout template
│   ├── header.html         # Navbar & announcement banner
│   ├── footer.html         # Footer layout
│   ├── index.html          # Homepage & collection hero
│   ├── shop.html           # Product catalog & order modal
│   ├── custom-order.html   # Custom order request form
│   ├── cart.html           # Shopping cart view
│   ├── checkout.html       # Order checkout view
│   ├── contact.html        # Contact form
│   └── about.html          # Brand story page
├── .env.example            # Sample environment variables
├── main.py                 # Core Flask application & routing
├── migrate_to_neon.py      # SQLite-to-Neon migration utility
├── requirements.txt        # Python package dependencies
└── vercel.json             # Vercel serverless configuration
```

---

## 📄 License
MIT License © Neetzmadeit
