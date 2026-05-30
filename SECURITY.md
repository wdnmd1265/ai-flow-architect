# Security Policy

## Supported Versions

The following versions of Audison are currently supported with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 2.5.x   | :white_check_mark: |
| 2.4.x   | :white_check_mark: |
| 2.3.x   | :white_check_mark: |
| < 2.3   | :x:                |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability in Audison,
please report it responsibly.

**Do NOT open a public GitHub Issue for security vulnerabilities.**

### Reporting Process

Send an email to: **audison.maintainer@proton.me**

Please include as much of the following information as possible:

- A detailed description of the vulnerability
- Steps to reproduce the issue
- Affected version(s)
- Potential impact
- Any suggested mitigations or fixes (optional)

### What to Expect

- **Initial Response**: Within 48 hours of your report
- **Status Update**: Within 5 business days, with our assessment and expected resolution timeline
- **Resolution**: We will work with you to validate and address the issue, and coordinate a public disclosure timeline

We appreciate your help in keeping Audison and its users safe.

## Scope

The following types of vulnerabilities fall within the scope of this security policy:

- **API Key Leakage**: Unintended exposure of API keys through logs, reports, error messages, or exported files
- **Prompt Injection**: Bypassing or manipulating the adversarial audit prompts
- **Command Injection**: Unsanitized input reaching shell/execution contexts
- **Credential Leakage**: Sensitive data appearing in audit outputs, reports, or logs
- **Supply Chain**: Vulnerabilities in third-party dependencies that affect Audison's security

## Out of Scope

The following are not considered security vulnerabilities in the context of Audison:

- **LLM Hallucinations**: The tool exists to detect these; false negatives or positives in detection are quality issues, not security vulnerabilities
- **Rate Limiting**: API provider rate limits affecting audit performance
- **Model-Specific Behaviors**: Variations in output between different LLM providers

## Disclosure Policy

We follow a coordinated disclosure process:

1. The reporter submits the vulnerability via email
2. We acknowledge receipt within 48 hours
3. We validate and develop a fix
4. We agree on a public disclosure date
5. We publish the advisory and credit the reporter (unless anonymity is requested)

## Hall of Fame

We maintain a list of security researchers who have responsibly disclosed vulnerabilities. If you wish to be recognized, please let us know in your report.