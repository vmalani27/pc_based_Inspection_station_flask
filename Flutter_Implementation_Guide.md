# Flutter Implementation Guide - Session-Based User Entry

## Overview
This guide shows how to implement the session-based user entry system in Flutter to prevent incomplete user records from being saved when users exit without calibrating.

## Key Changes
- User login creates a temporary session
- Only completed calibrations commit to permanent records
- Session management prevents data pollution

---

## 1. Data Models

```dart
// lib/models/user_session.dart
class UserSession {
  final String sessionId;
  final String rollNumber;
  final String name;
  final DateTime createdAt;
  final String status; // 'pending_calibration', 'calibrated', 'expired'
  final bool calibrationRequired;

  UserSession({
    required this.sessionId,
    required this.rollNumber,
    required this.name,
    required this.createdAt,
    required this.status,
    required this.calibrationRequired,
  });

  factory UserSession.fromJson(Map<String, dynamic> json) {
    return UserSession(
      sessionId: json['session_id'],
      rollNumber: json['roll_number'],
      name: json['name'],
      createdAt: DateTime.parse(json['created_at']),
      status: json['status'],
      calibrationRequired: json['calibration_required'],
    );
  }
}

// lib/models/login_response.dart
class LoginResponse {
  final String sessionId;
  final String status; // 'new_user' or 'welcome_back'
  final bool shouldCalibrate;
  final String message;

  LoginResponse({
    required this.sessionId,
    required this.status,
    required this.shouldCalibrate,
    required this.message,
  });

  factory LoginResponse.fromJson(Map<String, dynamic> json) {
    return LoginResponse(
      sessionId: json['session_id'],
      status: json['status'],
      shouldCalibrate: json['should_calibrate'],
      message: json['message'],
    );
  }
}
```

---

## 2. Session Service

```dart
// lib/services/session_service.dart
import 'package:shared_preferences/shared_preferences.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class SessionService {
  static const String SESSION_KEY = 'user_session_id';
  static const String BASE_URL = 'https://pcbis.flashstudios.tech'; // Your API URL

  // Store session ID locally
  static Future<void> storeSessionId(String sessionId) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(SESSION_KEY, sessionId);
  }

  // Get stored session ID
  static Future<String?> getSessionId() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(SESSION_KEY);
  }

  // Clear session ID
  static Future<void> clearSession() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(SESSION_KEY);
  }

  // Check if user has active session
  static Future<bool> hasActiveSession() async {
    final sessionId = await getSessionId();
    return sessionId != null;
  }

  // Create user session (login)
  static Future<LoginResponse?> createUserSession({
    required String rollNumber,
    required String name,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$BASE_URL/user_entry'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'roll_number': rollNumber,
          'name': name,
        }),
      );

      if (response.statusCode == 200) {
        final loginResponse = LoginResponse.fromJson(jsonDecode(response.body));
        
        // Store session ID locally
        await storeSessionId(loginResponse.sessionId);
        
        return loginResponse;
      }
      return null;
    } catch (e) {
      print('Error creating session: $e');
      return null;
    }
  }

  // Complete calibration and finalize user entry
  static Future<bool> completeCalibration() async {
    try {
      final sessionId = await getSessionId();
      if (sessionId == null) {
        print('No active session found');
        return false;
      }

      final response = await http.post(
        Uri.parse('$BASE_URL/user_entry/complete_calibration'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'session_id': sessionId}),
      );

      if (response.statusCode == 200) {
        final result = jsonDecode(response.body);
        
        if (result['status'] == 'calibration_completed') {
          // Clear session from local storage
          await clearSession();
          return true;
        }
      }
      return false;
    } catch (e) {
      print('Error completing calibration: $e');
      return false;
    }
  }

  // Get session status
  static Future<UserSession?> getSessionStatus() async {
    try {
      final sessionId = await getSessionId();
      if (sessionId == null) return null;

      final response = await http.get(
        Uri.parse('$BASE_URL/user_entry/session/$sessionId'),
      );

      if (response.statusCode == 200) {
        return UserSession.fromJson(jsonDecode(response.body));
      } else {
        // Session expired or invalid, clear it
        await clearSession();
        return null;
      }
    } catch (e) {
      print('Error getting session status: $e');
      await clearSession(); // Clear invalid session
      return null;
    }
  }
}
```

---

## 3. Updated Login Screen

```dart
// lib/screens/login_screen.dart
import 'package:flutter/material.dart';
import '../services/session_service.dart';
import '../models/login_response.dart';

class LoginScreen extends StatefulWidget {
  @override
  _LoginScreenState createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final TextEditingController rollNumberController = TextEditingController();
  final TextEditingController nameController = TextEditingController();
  bool isLoading = false;

  @override
  void initState() {
    super.initState();
    _checkExistingSession();
  }

  // Check if user has an active session on app start
  Future<void> _checkExistingSession() async {
    final session = await SessionService.getSessionStatus();
    
    if (session != null) {
      if (session.status == 'pending_calibration') {
        // User has incomplete session, navigate to calibration
        _navigateToCalibration(session.calibrationRequired);
      } else if (session.status == 'calibrated') {
        // Session completed, clean up and proceed
        await SessionService.clearSession();
        _navigateToMainApp();
      }
    }
  }

  // Handle user login
  Future<void> _handleLogin() async {
    if (rollNumberController.text.isEmpty || nameController.text.isEmpty) {
      _showError('Please fill all fields');
      return;
    }

    setState(() {
      isLoading = true;
    });

    try {
      final loginResponse = await SessionService.createUserSession(
        rollNumber: rollNumberController.text,
        name: nameController.text,
      );

      if (loginResponse != null) {
        _showSuccess('Session created: ${loginResponse.message}');
        
        // Navigate based on calibration requirement
        if (loginResponse.shouldCalibrate) {
          _navigateToCalibration(true);
        } else {
          // Even if calibration not required, still complete the session
          final success = await SessionService.completeCalibration();
          if (success) {
            _navigateToMainApp();
          } else {
            _showError('Failed to complete login');
          }
        }
      } else {
        _showError('Login failed');
      }
    } catch (e) {
      _showError('Error: $e');
    }

    setState(() {
      isLoading = false;
    });
  }

  void _navigateToCalibration(bool isRequired) {
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(
        builder: (context) => CalibrationScreen(isRequired: isRequired),
      ),
    );
  }

  void _navigateToMainApp() {
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(
        builder: (context) => MainAppScreen(),
      ),
    );
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: Colors.red),
    );
  }

  void _showSuccess(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: Colors.green),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('PC-Based Inspection Station')),
      body: Padding(
        padding: EdgeInsets.all(16.0),
        child: Column(
          children: [
            TextField(
              controller: rollNumberController,
              decoration: InputDecoration(
                labelText: 'Roll Number',
                border: OutlineInputBorder(),
              ),
            ),
            SizedBox(height: 16),
            TextField(
              controller: nameController,
              decoration: InputDecoration(
                labelText: 'Name',
                border: OutlineInputBorder(),
              ),
            ),
            SizedBox(height: 24),
            ElevatedButton(
              onPressed: isLoading ? null : _handleLogin,
              child: isLoading 
                ? CircularProgressIndicator() 
                : Text('Login'),
              style: ElevatedButton.styleFrom(
                minimumSize: Size(double.infinity, 48),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
```

---

## 4. Updated Calibration Screen

```dart
// lib/screens/calibration_screen.dart
import 'package:flutter/material.dart';
import '../services/session_service.dart';

class CalibrationScreen extends StatefulWidget {
  final bool isRequired;

  CalibrationScreen({required this.isRequired});

  @override
  _CalibrationScreenState createState() => _CalibrationScreenState();
}

class _CalibrationScreenState extends State<CalibrationScreen> {
  bool isCalibrating = false;
  bool isCompleting = false;

  // Simulate device check
  Future<bool> _checkDevice() async {
    // Your device check logic here
    await Future.delayed(Duration(seconds: 2));
    return true; // Return actual check result
  }

  // Simulate calibration process
  Future<bool> _performCalibration() async {
    setState(() {
      isCalibrating = true;
    });

    try {
      // Your calibration logic here
      await Future.delayed(Duration(seconds: 5));
      
      // Simulate calibration result
      bool calibrationSuccess = true; // Your actual result
      
      return calibrationSuccess;
    } finally {
      setState(() {
        isCalibrating = false;
      });
    }
  }

  // Complete calibration and finalize user entry
  Future<void> _completeCalibration() async {
    setState(() {
      isCompleting = true;
    });

    try {
      final calibrationSuccess = await _performCalibration();
      
      if (calibrationSuccess) {
        // Complete the session on backend
        final sessionCompleted = await SessionService.completeCalibration();
        
        if (sessionCompleted) {
          _showSuccess('Calibration completed! Login finalized.');
          
          // Navigate to main app after delay
          await Future.delayed(Duration(seconds: 2));
          _navigateToMainApp();
        } else {
          _showError('Failed to complete session');
        }
      } else {
        _showError('Calibration failed. Please try again.');
      }
    } catch (e) {
      _showError('Error during calibration: $e');
    }

    setState(() {
      isCompleting = false;
    });
  }

  void _navigateToMainApp() {
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(
        builder: (context) => MainAppScreen(),
      ),
    );
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: Colors.red),
    );
  }

  void _showSuccess(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: Colors.green),
    );
  }

  @override
  Widget build(BuildContext context) {
    return WillPopScope(
      // Prevent back navigation during calibration
      onWillPop: () async => !isCalibrating && !isCompleting,
      child: Scaffold(
        appBar: AppBar(
          title: Text('Device Calibration'),
          automaticallyImplyLeading: false, // Remove back button
        ),
        body: Padding(
          padding: EdgeInsets.all(16.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.settings,
                size: 80,
                color: Theme.of(context).primaryColor,
              ),
              SizedBox(height: 24),
              Text(
                widget.isRequired 
                  ? 'Calibration Required' 
                  : 'Calibration Recommended',
                style: Theme.of(context).textTheme.headlineSmall,
                textAlign: TextAlign.center,
              ),
              SizedBox(height: 16),
              Text(
                'Please calibrate the device before proceeding to ensure accurate measurements.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 16),
              ),
              SizedBox(height: 32),
              
              // Check Device Button
              ElevatedButton.icon(
                onPressed: isCalibrating || isCompleting ? null : _checkDevice,
                icon: Icon(Icons.search),
                label: Text('Check Device'),
                style: ElevatedButton.styleFrom(
                  minimumSize: Size(double.infinity, 48),
                  backgroundColor: Colors.blue,
                ),
              ),
              
              SizedBox(height: 16),
              
              // Calibrate Button
              ElevatedButton.icon(
                onPressed: isCalibrating || isCompleting ? null : _completeCalibration,
                icon: isCalibrating || isCompleting
                  ? SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                      ),
                    )
                  : Icon(Icons.tune),
                label: Text(
                  isCalibrating 
                    ? 'Calibrating...' 
                    : isCompleting 
                      ? 'Completing...' 
                      : 'Calibrate & Complete Login'
                ),
                style: ElevatedButton.styleFrom(
                  minimumSize: Size(double.infinity, 48),
                  backgroundColor: Colors.green,
                ),
              ),
              
              SizedBox(height: 24),
              
              // Warning message
              Container(
                padding: EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.orange.withOpacity(0.1),
                  border: Border.all(color: Colors.orange),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    Icon(Icons.warning, color: Colors.orange),
                    SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        'Your login will only be saved after successful calibration.',
                        style: TextStyle(color: Colors.orange[800]),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
```

---

## 5. App Lifecycle Management

```dart
// lib/services/app_lifecycle_service.dart
import 'package:flutter/material.dart';
import 'session_service.dart';

class AppLifecycleService extends WidgetsBindingObserver {
  static final AppLifecycleService _instance = AppLifecycleService._internal();
  factory AppLifecycleService() => _instance;
  AppLifecycleService._internal();

  void initialize() {
    WidgetsBinding.instance.addObserver(this);
  }

  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    super.didChangeAppLifecycleState(state);
    
    switch (state) {
      case AppLifecycleState.paused:
        _handleAppPaused();
        break;
      case AppLifecycleState.resumed:
        _handleAppResumed();
        break;
      case AppLifecycleState.detached:
        _handleAppClosed();
        break;
      default:
        break;
    }
  }

  void _handleAppPaused() {
    // App is paused - could save state here
    print('App paused - user session may be incomplete');
  }

  void _handleAppResumed() async {
    // Check for incomplete sessions when app resumes
    final session = await SessionService.getSessionStatus();
    if (session != null && session.status == 'pending_calibration') {
      // Could show notification or redirect to calibration
      print('Incomplete session found on resume');
    }
  }

  void _handleAppClosed() {
    // App is closing - incomplete sessions will auto-expire on backend
    print('App closing - incomplete sessions will expire');
  }
}
```

---

## 6. Main App Integration

```dart
// lib/main.dart
import 'package:flutter/material.dart';
import 'services/app_lifecycle_service.dart';
import 'screens/login_screen.dart';

void main() {
  runApp(MyApp());
}

class MyApp extends StatefulWidget {
  @override
  _MyAppState createState() => _MyAppState();
}

class _MyAppState extends State<MyApp> {
  final AppLifecycleService _lifecycleService = AppLifecycleService();

  @override
  void initState() {
    super.initState();
    _lifecycleService.initialize();
  }

  @override
  void dispose() {
    _lifecycleService.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'PC-Based Inspection Station',
      theme: ThemeData(
        primarySwatch: Colors.blue,
        visualDensity: VisualDensity.adaptivePlatformDensity,
      ),
      home: LoginScreen(),
    );
  }
}
```

---

## 7. Dependencies to Add

Add these to your `pubspec.yaml`:

```yaml
dependencies:
  flutter:
    sdk: flutter
  http: ^0.13.5
  shared_preferences: ^2.0.15
  # Add any other dependencies you need
```

---

## Key Benefits

✅ **Clean Data**: Only completed workflows create permanent records
✅ **Session Recovery**: Users can resume incomplete sessions  
✅ **Auto Cleanup**: Sessions expire automatically (1 hour)
✅ **Better UX**: Clear feedback on session status
✅ **Data Integrity**: No incomplete user entries in database

## Testing the Flow

1. **Complete Flow**: Login → Calibrate → Success ✅
2. **Incomplete Flow**: Login → Exit → No permanent record ✅
3. **Resume Flow**: Login → Exit → Reopen → Resume session ✅
4. **Session Expiry**: Login → Wait 1+ hour → Session expired ✅

This implementation ensures that only users who complete the full calibration process get permanent entries in your system.
