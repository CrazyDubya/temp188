# Claude Memory for EnterTheConvo Project

## CRITICAL SECURITY REMINDER: GUARD AGAINST REWARD HACKING

**⚠️ ALWAYS VERIFY - NO SHORTCUTS OR CHEATS ALLOWED ⚠️**

### What is Reward Hacking in Testing Context:
- Creating tests that automatically pass without testing real functionality
- Simplifying or mutilating code to make tests pass easier
- Writing mock implementations that bypass actual business logic
- Editing production code to remove complexity just to make testing easier
- Creating "happy path only" tests that ignore edge cases and error conditions

### Security Checklist - VERIFY EVERY 3rd STEP:
1. ✅ Are tests actually calling the real implementation?
2. ✅ Do tests fail when they should (negative test cases)?
3. ✅ Is the production code unchanged and not simplified?
4. ✅ Are mocks limited to external dependencies only (database, Redis, external APIs)?
5. ✅ Do tests cover error conditions, edge cases, and security scenarios?
6. ✅ Are authentication/authorization checks being properly tested?
7. ✅ Do integration tests use real database operations?
8. ✅ Are rate limiting and security middleware actually being tested?

### RED FLAGS - STOP IMMEDIATELY IF YOU SEE:
- Tests that always return `true` or skip actual validation
- Production code modified to be "more testable" by removing security checks
- Mock implementations that are simpler than real implementations
- Tests that don't actually call the functions they claim to test
- Database operations mocked away in integration tests
- Authentication/authorization bypassed in tests
- Error conditions not tested

### MANDATE: 
- Every 3rd completed task MUST include a security verification step
- Tests MUST fail when expected functionality is broken
- Production code integrity MUST be maintained
- Real business logic MUST be tested, not simplified versions

## Project Context

### Current Status:
- Secure admin panel with CRUD operations implemented
- Security vulnerabilities removed (admin-token endpoint, admin-test.html)
- Room deletion and audit log access functionality complete
- All dangerous reward hacks removed from codebase

### Testing Requirements:
- Building comprehensive automated test suite
- Testing authentication, authorization, CRUD operations
- Verifying security middleware and rate limiting
- Testing audit logging and admin functionality

### Key Components to Test:
- Authentication system (JWT, API keys, OAuth)
- Room management with permissions
- User management and roles
- Message CRUD operations
- Admin panel functionality
- Security middleware
- Rate limiting
- Audit logging

### Security-Critical Areas:
- Authentication flows must be tested without bypasses
- Authorization checks must verify real permission logic
- Database operations must use real SQL queries in integration tests
- Rate limiting must actually limit requests
- Audit logging must capture real events

## Commands for Testing:
- Test command: `npm test` (to be set up)
- Development server: Located at `/var/entertheconvo.com/entertheconvo-backend/`
- Database: SQLite at `entertheconvo.db`
- Main server file: `src/server.js`
- Admin routes: `src/routes/admin.js`

## REMEMBER: Quality over speed. Real tests over fake ones. Security over convenience.