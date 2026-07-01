# Oracle Design Overview

# **Oracle**

### **Design Overview**

**Version 0.1**

## **Purpose**

Oracle is a platform for understanding how a website is perceived by search engines, AI systems, and other information sources.

Unlike traditional SEO tools, Oracle separates the collection of evidence from the interpretation of that evidence.

The database represents objective observations.

The dashboard and Oracle AI provide subjective analysis.

---

# **Core Philosophy**

Every component has a single responsibility.

Discover  
   Learn the website.

Monitor  
   Observe external sources.

Dashboard  
   Present information and allow human evaluation.

Oracle  
   Analyze observations and recommend actions.

Each component may evolve independently.

---

# **Discover**

Discover is responsible for understanding the website itself.

Inputs

* Sitemap  
* Website pages

Outputs

* Pages  
* Metadata  
* Candidate search queries  
* Relationships between pages and queries

Discover does **not**

* Contact search engines  
* Measure rankings  
* Interpret results  
* Recommend changes

Discover is run initially and whenever significant website content is added or reorganized.

---

# **Monitor**

Monitor observes how external systems perceive the website.

Each monitor is independent.

Examples

* Google Organic  
* Google AI Overview  
* Bing  
* Perplexity  
* ChatGPT  
* Gemini  
* Future sources

A monitor simply

* Reads active queries from the database  
* Contacts its source  
* Records observations

Monitors never interpret results.

They only collect evidence.

---

# **Dashboard**

Dashboard is the user's workspace.

Responsibilities

* Display observations  
* Display trends  
* Compare sources  
* Edit pages  
* Edit queries  
* Enable or disable monitoring  
* Adjust scoring models  
* Explore historical data

Dashboard never collects information from external systems.

It only works with the Oracle database.

---

# **Oracle**

Oracle is the intelligence layer.

Its purpose is not to report data.

Its purpose is to answer the question:

What should I do next?

Oracle examines

* Website structure  
* Historical observations  
* Trends  
* User scoring models

Oracle then produces

* Recommendations  
* Opportunities  
* Warnings  
* Suggested actions

Oracle should explain its reasoning whenever possible.

---

# **Sources**

A source is any external observer.

Examples

* Google Organic  
* Google AI Overview  
* Bing  
* Perplexity  
* ChatGPT  
* Gemini

Oracle treats every source equally.

Sources simply observe the website from different perspectives.

---

# **Database Philosophy**

The database stores facts.

Examples

* Pages  
* Queries  
* Observations  
* Rankings  
* Citations  
* Dates  
* Raw responses

The database does **not** determine importance.

---

# **Scoring**

Scoring belongs entirely to Dashboard.

Users decide what matters.

Examples

Google AI Overview      50

Google Organic          40

Perplexity              30

Bing                    10

Users may also determine

* Position weighting  
* AI citation weighting  
* Page-two penalties  
* Overall source importance

Changing a scoring model never changes the underlying observations.

---

# **Workflow**

Discover

↓

Dashboard

Review pages  
Review generated queries  
Add/Edit/Delete/Disable queries

↓

Monitor

Collect observations

↓

Dashboard

Analyze results

↓

Oracle

Recommend actions

↓

Repeat Monitor

Discover is typically run only after significant additions or changes to the website.

Monitor may be run daily or on demand.

---

# **Guiding Principle**

Oracle is not an SEO tool.

Oracle is a knowledge platform.

It first learns what the website is trying to communicate.

It then observes how the outside world perceives that communication.

Finally, it helps the user improve the alignment between those two perspectives.

