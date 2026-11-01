# TRUSTED_PROXY Analysis for Render Deployment

## Current Implementation

The codebase parses `X-Forwarded-For` in `app/api/ratelimit.py`:

```python
def client_ip(request: Request, trusted_proxy: bool) -> str:
    """X-Forwarded-For is trusted only when TRUSTED_PROXY=true, otherwise a
    client could forge its own rate-limit bucket by sending the header."""
    if trusted_proxy:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip() or "unknown"
    return request.client.host if request.client else "unknown"
```

### How It Works
- When `TRUSTED_PROXY=true`: Extracts the first IP from `X-Forwarded-For` header
- When `TRUSTED_PROXY=false`: Uses the direct socket IP (`request.client.host`)

## What `X-Forwarded-For` Contains

The `X-Forwarded-For` (XFF) header is a de-facto standard for identifying the originating client IP when requests pass through proxies/load balancers. It is formatted as:

```
X-Forwarded-For: client, proxy1, proxy2
```

- **First IP**: Original client IP
- **Subsequent IPs**: Each proxy that forwarded the request

## Render's Proxy Behavior

Render uses a managed load balancer / proxy infrastructure. When enabled:

1. **Render sets the XFF header** on inbound requests before they reach your application
2. The header contains the actual client IP as the first entry
3. Multiple proxies in Render's infrastructure may append their IPs

## Security Assessment: Is `TRUSTED_PROXY=true` Safe on Render?

### ✅ SAFE IF:
- Render is the **only** proxy between the client and your application
- You trust Render's infrastructure (which is generally appropriate since you're hosting on Render)
- The application has no other entry points that could inject XFF headers

### ⚠️ NOT SAFE IF:
- The application is behind additional proxies beyond Render that you don't control
- The application accepts traffic from sources that could set arbitrary headers
- There are unsecured paths that bypass Render's proxy

### Key Risk: IP Spoofing

If `TRUSTED_PROXY=true` is set without ensuring Render is the sole proxy:

> **An attacker could forge their rate-limit bucket by sending:**
> ```
> X-Forwarded-For: 10.0.0.1
> ```
> 
> This would make the rate limiter track them as IP 10.0.0.1 instead of their real IP.

## Recommendation for This Application

Given this application's current architecture:

1. **Staging stays `false` as requested** - safer default, no XFF trust
2. **For production on Render**: `TRUSTED_PROXY=true` is likely safe IF:
   - The only entry point is Render's proxy (no direct IP access)
   - No other untrusted proxies sit between Render and the app
3. **Verification needed**: Check Render dashboard that there's no additional proxy/CDN layer that could inject XFF

## Implementation Gaps

### Current implementation weaknesses:

1. **No proxy chain validation**: The code trusts the first XFF entry unconditionally. A more robust implementation would:
   - Verify the request came from a trusted proxy IP range before trusting XFF
   - Use `X-Real-IP` or `CF-Connecting-IP` (Cloudflare) as an alternative

2. **No `X-Forwarded-Proto` handling**: For HTTPS-aware applications, the proto header should also be considered

3. **Rate limit bucket uses raw IP string**: The code normalizes user IDs but not IPs. Different representations of the same IP (IPv4 vs IPv6-mapped, with/without port) could create separate buckets.

## Conclusion

**`TRUSTED_PROXY=true` is conditionally safe behind Render's proxy**, but only if:
- Render is the sole ingress point
- You've verified no additional proxy layers exist
- You understand that any request reaching your app is already behind Render's proxy

**For staging**: Keep `false` as you specified. The rate limiter still works—it just uses the direct connection IP, which on Render will be Render's internal IP, making per-IP rate limiting effectively per-instance.

**For production**: Once deployed, verify the proxy chain and set `true` if Render is the only proxy.
