// ==UserScript==
// @name         JobHunt — LinkedIn Extractor
// @namespace    https://github.com/your-username/jobhunt
// @version      1.0.0
// @description  Select text on LinkedIn → Cmd+Shift+X → Send to local JobHunt server
// @author       Your Name
// @match        *://www.linkedin.com/*
// @match        *://linkedin.com/*
// @grant        GM_xmlhttpRequest
// @grant        GM_addStyle
// @connect      127.0.0.1
// @connect      localhost
// @run-at       document-idle
// ==/UserScript==

(function() {
    'use strict';

    // Configuration
    const WEBHOOK_URL = "http://127.0.0.1:8000/webhook";
    const REQUEST_TIMEOUT_MS = 30000; // Increased to 30 seconds to allow LLM time to generate draft
    const TOAST_DURATION_MS = 3000;

    // Toast styles
    GM_addStyle(`
        .jobhunt-toast {
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 8px;
            color: white;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            font-size: 14px;
            font-weight: 500;
            z-index: 999999;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            transition: all 0.3s ease;
            transform: translateY(100px);
            opacity: 0;
            pointer-events: none;
        }
        .jobhunt-toast.show {
            transform: translateY(0);
            opacity: 1;
        }
        .jobhunt-toast.info {
            background-color: #0077b5; /* LinkedIn Blue */
        }
        .jobhunt-toast.success {
            background-color: #059669; /* Emerald 600 */
        }
        .jobhunt-toast.error {
            background-color: #dc2626; /* Red 600 */
        }
    `);

    // Toast manager
    let currentToastTimeout = null;

    function showToast(message, type = 'info') {
        let toast = document.getElementById('jobhunt-toast');
        
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'jobhunt-toast';
            toast.className = `jobhunt-toast ${type}`;
            document.body.appendChild(toast);
        } else {
            toast.className = `jobhunt-toast ${type}`;
        }

        toast.textContent = message;
        
        // Force reflow
        void toast.offsetWidth;
        
        toast.classList.add('show');

        if (currentToastTimeout) {
            clearTimeout(currentToastTimeout);
        }

        currentToastTimeout = setTimeout(() => {
            toast.classList.remove('show');
        }, TOAST_DURATION_MS);
    }

    async function computeHash(text) {
        const msgUint8 = new TextEncoder().encode(text);
        const hashBuffer = await crypto.subtle.digest('SHA-256', msgUint8);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
        return hashHex;
    }

    function sendToServer(selectedText, pageUrl, contentHash) {
        showToast("Sending to JobHunt...", "info");
        
        const payload = {
            selected_text: selectedText,
            page_url: pageUrl,
            content_hash: contentHash,
            timestamp: new Date().toISOString()
        };

        GM_xmlhttpRequest({
            method: "POST",
            url: WEBHOOK_URL,
            headers: {
                "Content-Type": "application/json"
            },
            data: JSON.stringify(payload),
            timeout: REQUEST_TIMEOUT_MS,
            onload: function(response) {
                if (response.status >= 200 && response.status < 300) {
                    try {
                        const json = JSON.parse(response.responseText);
                        if (json.status === "skipped" && json.reason === "duplicate_post") {
                            showToast("Already processed this post.", "info");
                        } else {
                            showToast("✅ Sent! Check your terminal.", "success");
                        }
                    } catch (e) {
                        showToast("✅ Sent! Check your terminal.", "success");
                    }
                } else if (response.status === 409) {
                    showToast("Already processed this post.", "info");
                } else {
                    console.error("[JobHunt] Error response:", response);
                    showToast(`❌ Failed: Server error (${response.status})`, "error");
                }
            },
            onerror: function(error) {
                console.error("[JobHunt] Network error:", error);
                showToast("❌ Failed: Server not running?", "error");
            },
            ontimeout: function() {
                console.error("[JobHunt] Request timed out");
                showToast("⏳ Server not responding", "error");
            }
        });
    }

    // Debounce manager
    let isProcessing = false;

    // Keyboard listener for Cmd+Shift+X / Ctrl+Shift+X
    document.addEventListener('keydown', async function(e) {
        // 'X' is keyCode 88, or use e.code === 'KeyX'
        if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.code === 'KeyX') {
            e.preventDefault(); // Prevent any default browser action

            if (isProcessing) {
                return;
            }

            const selectedText = window.getSelection().toString().trim();
            if (!selectedText) {
                showToast("❌ No text selected! Highlight some text first.", "error");
                return;
            }

            const pageUrl = window.location.href;
            const contentHash = await computeHash(selectedText);
            
            isProcessing = true;
            sendToServer(selectedText, pageUrl, contentHash);
            
            // Release lock after 2 seconds (debounce)
            setTimeout(() => {
                isProcessing = false;
            }, 2000);
        }
    });

    console.log("[JobHunt] Extractor loaded. Listening for Cmd+Shift+X");
})();
