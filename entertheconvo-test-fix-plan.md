# EnterTheConvo Test Fix Plan
**Created:** 2025-01-27
**Status:** Active
**Failures:** 95/137 tests failing

## 🚨 ANTI-REWARD-HACKING PROTOCOL
**CRITICAL SECURITY MANDATE:** 
- ✅ Every 3rd task MUST include verification that tests are testing REAL functionality
- ❌ NO simplifying production code to make tests pass
- ❌ NO mock bypassing of actual business logic  
- ❌ NO auto-pass test patterns (expect(true).toBe(true))
- ✅ All database operations must use REAL SQL queries
- ✅ Authentication/authorization checks must be ACTUALLY tested
- ✅ Integration tests must use REAL database operations

## 📊 Current State Analysis
- **Total Tests:** 137 (42 passing, 95 failing)
- **Failed Suites:** 7/9
- **Main Issues:** Database schema mismatches, 500 errors, authentication problems

## 🎯 Phase 1: Database Schema Foundation (HIGH PRIORITY)
**Goal:** Fix fundamental database schema mismatches causing 500 errors

### Task 1.1: Audit Complete Database Schema Differences
- [ ] Compare production schema vs test schema for ALL tables
- [ ] Document every missing column, wrong type, missing table
- [ ] Verify foreign key relationships match
- **Security Check:** Ensure this doesn't simplify any table structures

### Task 1.2: Fix API Keys Table Schema 
- [ ] Add missing columns in test database (key_prefix, revoked_at, etc.)
- [ ] Fix data types to match production
- [ ] Test API key CRUD operations work with real database queries
- **Security Check:** Verify API key authentication actually validates real keys

### Task 1.3: Fix Users Table Schema Alignment
- [ ] Ensure all production columns exist in test (github_id, avatar_url, bio, etc.)
- [ ] Fix constraint issues causing UNIQUE failures
- [ ] Implement proper test data cleanup between tests
- **Security Check:** Verify user creation tests don't bypass password hashing

## 🎯 Phase 2: API Key Management System (HIGH PRIORITY)
**Goal:** Fix complete API key system failure (all tests failing with 500 errors)

### Task 2.1: Fix API Key Controller Database Queries
- [ ] Audit authController.createAPIKey for database query issues
- [ ] Fix SQLite vs PostgreSQL syntax problems
- [ ] Ensure test database connection is used properly
- **Security Check:** Verify API key generation uses real crypto, not simplified version

### Task 2.2: Fix API Key Authentication Middleware
- [ ] Debug API key validation in auth middleware
- [ ] Fix database connection handling for API key lookup
- [ ] Test API key permission enforcement
- **Security Check:** Verify API keys actually limit permissions, no bypass

### Task 2.3: API Key Route Integration
- [ ] Fix /api/apikeys route authentication
- [ ] Test API key listing, creation, deletion
- [ ] Verify proper error handling
- **Security Check:** Ensure admin-only operations require real admin role

## 🎯 Phase 3: Room Management System (HIGH PRIORITY)  
**Goal:** Fix 84 failing room tests (creation, permissions, CRUD)

### Task 3.1: Fix Room Creation Authentication
- [ ] Debug why authenticated room creation returns 401
- [ ] Fix authentication middleware application to room routes
- [ ] Test both public and private room creation
- **Security Check:** Verify room creation actually checks user limits

### Task 3.2: Room Permission System
- [ ] Fix room_permissions table queries
- [ ] Test read/write/admin permission enforcement
- [ ] Fix public vs private room access logic
- **Security Check:** Ensure private rooms truly block unauthorized access

### Task 3.3: Room CRUD Operations
- [ ] Fix room listing, updating, deletion
- [ ] Test pagination and filtering
- [ ] Fix room statistics and member counting
- **Security Check:** Verify room deletion actually removes data, no fake success

## 🎯 Phase 4: User Management & Admin Operations (MEDIUM PRIORITY)
**Goal:** Fix user management 500 errors and constraint failures

### Task 4.1: User Management Database Issues  
- [ ] Fix UNIQUE constraint failures in test user creation
- [ ] Implement proper test data isolation
- [ ] Fix user deletion cascade operations
- **Security Check:** Verify user deletion actually removes sensitive data

### Task 4.2: Admin Panel Operations
- [ ] Fix admin user management endpoints
- [ ] Test role assignment and permission changes
- [ ] Fix audit logging foreign key issues
- **Security Check:** Ensure admin operations require real admin authentication

## 🎯 Phase 5: Authorization & Audit System (MEDIUM PRIORITY)
**Goal:** Fix authorization middleware and audit logging

### Task 5.1: Authorization Middleware Fixes
- [ ] Fix 401/403 error inconsistencies  
- [ ] Test role-based access control
- [ ] Fix permission checking logic
- **Security Check:** Verify authorization actually blocks unauthorized actions

### Task 5.2: Audit Logging System
- [ ] Fix foreign key constraint failures in audit_logs
- [ ] Test audit log creation for all operations
- [ ] Fix SQLite/PostgreSQL syntax issues
- **Security Check:** Ensure audit logs capture real user actions, not fake events

## 🔄 Verification Protocol (Run Every 3rd Task)
1. **Real Functionality Check:** Run failing test, verify it fails when it should
2. **Database Verification:** Check that database operations use real SQL
3. **Security Validation:** Ensure authentication/authorization is actually tested
4. **Integration Test:** Verify end-to-end workflows work with real data
5. **Anti-Shortcut Audit:** Review recent changes for any test simplifications

## 📋 Task Execution Rules
1. **One task at a time** - Complete fully before moving to next
2. **Test after each fix** - Verify improvement without breaking others  
3. **Document breaking changes** - Note any production code modifications
4. **Real error handling** - Don't suppress errors, fix root causes
5. **Security first** - Every fix must maintain or improve security

## 🎯 Success Criteria
- [ ] All 95 failing tests pass with REAL functionality
- [ ] No production code simplified to accommodate tests
- [ ] All database operations use proper SQL queries
- [ ] Authentication/authorization fully functional
- [ ] Integration tests work end-to-end

## 📝 Progress Tracking
**Phase 1:** Not Started
**Phase 2:** Not Started  
**Phase 3:** Not Started
**Phase 4:** Not Started
**Phase 5:** Not Started

**Last Updated:** 2025-01-27
**Next Review:** After completing Phase 1, Task 1.3