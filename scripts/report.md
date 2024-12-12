# Progress Report: Secure Code Generation with LLMs

## 1. **Summary**  
We aim to determine whether **LLMs generate secure or vulnerable code** when addressing GitHub issues. Specifically, we are investigating:  
- Do LLMs introduce vulnerabilities when humans don’t?  
- Do human-written patches fix or introduce vulnerabilities?  

---

## 2. **Dataset Curation**  
To start, I curated a dataset of patches from the **SWE-Bench train set**. I retrieved the original and patched Python files corresponding to GitHub issues:  

### **Dataset Statistics**  
| State       | Projects | Commits | Files  |
|-------------|----------|---------|--------|
| Original    | 34       | 10,522  | 32,873 |
| Patched     | 34       | 10,590  | 35,000 |

- **Observation**: Patched files include new files added in commits, hence more files than in the original dataset.  

---

## 3. **Static Analysis Tools**  
I ran **CodeQL** and **Bandit** on both datasets to analyze vulnerabilities.  

- CodeQL took 16–17 hours, but one run failed due to storage limits. I restarted after optimizing.  
- Bandit completed much faster.  

---

## 4. **Results Summary**  

### **CodeQL Results**  
| **State**      | Total Vulnerabilities | Vulnerable Commits | Vulnerable Files |
|-----------------|-----------------------|--------------------|------------------|
| Original       | 642                   | 464                | 157              |
| Patched        | 672                   | 479                | 169              |

### **Bandit Results**  
| **State**      | Total Vulnerabilities | Vulnerable Commits | Vulnerable Files |
|-----------------|-----------------------|--------------------|------------------|
| Original       | 19,158                | 5,980              | 2,673            |
| Patched        | 19,696                | 6,055              | 2,882            |

---

### **Vulnerability Changes Between Original and Patched**  
I compared tool outputs to classify vulnerabilities as **persisting**, **new**, or **fixed**.

#### **CodeQL Changes**  
| Status       | Count |
|--------------|-------|
| Persisting   | 623   |
| New          | 49    |
| Fixed        | 19    |

#### **Bandit Changes**  
| Status       | Count  |
|--------------|--------|
| Persisting   | 18,829 |
| New          | 867    |
| Fixed        | 329    |

---

## 5. **Overlap Between Tools**  
Since Bandit has high false positives, I focused on vulnerabilities found **by both tools** in the same files and commits.

### **Intersection Results**  
| **Metric**               | Count |
|--------------------------|-------|
| Total Unique Vulns       | 176   |
| Unique Vulnerable Commits | 131   |
| Unique Vulnerable Files   | 54    |

#### **Overlap Status**  
| Status       | Count |
|--------------|-------|
| Persisting   | 183   |
| New          | 16    |
| Fixed        | 6     |

---

### **Examples of New Vulnerabilities**  
| **Name**                                                          | Frequency |
|------------------------------------------------------------------|-----------|
| Arbitrary file write during tarfile extraction                   | 4         |
| Overly permissive regular expression range                       | 3         |
| Default version of SSL/TLS may be insecure                       | 2         |
| Insecure temporary file                                          | 2         |
| Overly permissive file permissions                               | 2         |
| Use of insecure SSL/TLS version                                  | 2         |
| Use of broken cryptographic hashing algorithm on sensitive data  | 1         |

### **Examples of Fixed Vulnerabilities**  
| **Name**                                  | Frequency |
|-------------------------------------------|-----------|
| Arbitrary file write during tarfile extraction | 2         |
| Overly permissive regular expression range | 2         |
| Insecure temporary file                    | 1         |
| Overly permissive file permissions         | 1         |

---

## 6. **Key Observations**  
- **Limited Overlap**: Only 176 vulnerabilities were found by both tools, suggesting either tools differ in detection capabilities or one has more false positives.  
- **Tool Limitations**: Bandit finds the same vulnerability multiple times in a file, inflating counts. Bandit also seems to have a higher FP rate. 
- **File Renaming Issue**: Some "new" vulnerabilities (3) are false positives due to file moves/renames.

---

## 7. **Next Steps**  
1. **Address Tool Limitations**: Explore a third static analysis tool to validate findings further?  
2. **LLM-Generated Responses**: Start generating code using LLMs for the same issues and analyze if they introduce vulnerabilities.  
3. **Refine Comparison Scripts**: Account for renamed/moved files to avoid false positives.

---

