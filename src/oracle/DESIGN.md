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



---

# **Coding Principles**

These principles guide the evolution of Oracle. When multiple solutions are possible, these principles take precedence.

### Single Responsibility

Every module has one clearly defined responsibility.

A module should have one primary reason to change.

---

### Ownership

Behavior belongs with the component that owns the underlying data or workflow.

Avoid placing functionality where it is merely convenient.

---

### Clear Boundaries

Applications communicate through well-defined interfaces.

Avoid exposing database implementation details throughout the codebase.

---

### Facts vs. Interpretation

Store facts.

Interpret facts elsewhere.

The database stores observations, not opinions, rankings, or scoring decisions.

---

### Generic Before Specific

Components without Oracle-specific knowledge should remain generic.

Oracle-specific behavior belongs in Oracle modules.

---

### Command-Line First

Each application exposes its functionality through a consistent command-line interface.

New capabilities should normally become options of existing commands rather than new one-off utilities.

---

### Evolution Over Replacement

Prefer extending existing architecture over replacing it.

Design components so they can grow naturally.

---

### Naming Matters

Names should communicate responsibility.

A reader should understand a module's purpose from its name.

---

### Keep the Layers Honest

Discover does not monitor.

Monitor does not interpret.

Dashboard does not collect.

Oracle does not fabricate observations.

---

### Simplicity Wins

Choose the simplest design that preserves future flexibility.

Avoid abstraction until there is a demonstrated need.

---

### Follow the Direction of Knowledge

Information flows in one direction.

Website

↓

Discover

↓

Database

↓

Monitor

↓

Database

↓

Dashboard

↓

Oracle

Each layer depends only on information produced by earlier layers. Components should communicate through defined interfaces rather than reaching across architectural boundaries.

---

# **Scoring**

Scoring models are configured through Dashboard and stored in the database.

Dashboard and Oracle may use those models to interpret observations, but changing a scoring model never changes the underlying observations.


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

