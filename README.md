# IntelliMF

IntelliMF is a data-driven platform for analyzing optimal Systematic Investment Plan (SIP) frequencies across 37,000+ mutual fund schemes. It combines financial analytics with data mining to provide both scheme-level optimization and portfolio-level insights.

---

## Features

- 📊 **SIP Frequency Optimization**
  - Evaluates weekly, bi-weekly, monthly, and bi-monthly SIP strategies
  - Identifies optimal frequency based on historical NAV data

- 🔗 **Association Rule Mining (FP-Growth)**
  - Discovers frequently co-invested mutual funds
  - Generates portfolio-level insights from investor baskets

- 🗄️ **PostgreSQL Data Warehouse**
  - Stores schemes, admin metadata, and SIP transactions
  - Supports both analytics and application queries

- ⚙️ **Admin Panel**
  - Add/update scheme details
  - Insert SIP orders (used for association mining)

- 🌐 **Web Application**
  - Built with Flask API
  - Live platform: https://intellimf.pranavmanoj.in

---

## 🧠 Tech Stack

- **Backend:** Python, Flask  
- **Database:** PostgreSQL  
- **Analytics:** Pandas, NumPy  
- **Data Mining:** FP-Growth Algorithm  
- **Deployment:** Railway
