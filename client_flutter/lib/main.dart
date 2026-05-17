import 'package:flutter/material.dart';
import 'package:livekit_client/livekit_client.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:google_fonts/google_fonts.dart';
import 'package:flutter/foundation.dart';

void main() {
  // Ensure Flutter is initialized
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const SafeCallApp());
}

class SafeCallApp extends StatelessWidget {
  const SafeCallApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Safe Calling Client',
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: const Color(0xFF0F172A),
        textTheme: GoogleFonts.outfitTextTheme(ThemeData.dark().textTheme),
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF3B82F6),
          brightness: Brightness.dark,
        ),
      ),
      home: const CallScreen(),
    );
  }
}

class CallScreen extends StatefulWidget {
  const CallScreen({super.key});

  @override
  State<CallScreen> createState() => _CallScreenState();
}

class _CallScreenState extends State<CallScreen> with SingleTickerProviderStateMixin {
  Room? _room;
  EventsListener<RoomEvent>? _listener;
  bool _isConnecting = false;
  bool _isConnected = false;
  List<Participant> _participants = [];
  bool _isSafetyActive = false;
  bool _isRecording = false;
  bool _isTogglingRecording = false;
  late AnimationController _pulseController;
  final TextEditingController _nameController = TextEditingController();

  // Cloud-ready URL resolution.
  // For release APK, set via: flutter build apk --dart-define=BACKEND_URL=https://...
  // Falls back to local dev server when not set.
  String get _backendBase {
    const cloudUrl = String.fromEnvironment('BACKEND_URL');
    if (cloudUrl.isNotEmpty) return cloudUrl;
    if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
      return 'http://192.168.29.34:8000';
    }
    return 'http://127.0.0.1:8000';
  }

  String get _backendUrl => '$_backendBase/token/demo';
  String get _recordingBaseUrl => '$_backendBase/recording';

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _cleanup();
    _pulseController.dispose();
    _nameController.dispose();
    super.dispose();
  }

  Future<void> _cleanup() async {
    if (_listener != null) {
      await _listener!.dispose();
      _listener = null;
    }
    if (_room != null) {
      await _room!.disconnect();
      _room = null;
    }
  }

  Future<void> _connect() async {
    setState(() => _isConnecting = true);

    try {
      String requestUrl = '$_backendUrl?room=testroom';
      final customName = _nameController.text.trim();
      if (customName.isNotEmpty) {
        requestUrl += '&name=${Uri.encodeComponent(customName)}';
      }

      // Attempt connection to the new backend demo provisioning route
      final response = await http.get(Uri.parse(requestUrl))
          .timeout(const Duration(seconds: 10));
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final token = data['token'];
        final String livekitUrl = data['livekit_url'];

        _room = Room();
        _listener = _room!.createListener();
        _listener!.on<RoomEvent>((event) {
          _updateParticipants();
          setState(() {});
        });

        const roomOptions = RoomOptions(
          defaultAudioCaptureOptions: AudioCaptureOptions(
            echoCancellation: false,
            noiseSuppression: false,
            autoGainControl: false,
          ),
        );

        await _room!.connect(livekitUrl, token, roomOptions: roomOptions);
        await _room!.localParticipant?.setMicrophoneEnabled(true);

        setState(() {
          _isConnected = true;
          _isConnecting = false;
          _isSafetyActive = true;
        });
        _updateParticipants();
        
      } else {
        throw Exception('Server Error: ${response.statusCode}');
      }
    } catch (e) {
      debugPrint('Connection failed: $e');
      setState(() => _isConnecting = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to connect: $e'), backgroundColor: Colors.redAccent),
        );
      }
    }
  }

  Future<void> _disconnect() async {
    // Stop recording first if active
    if (_isRecording) await _toggleRecording();
    await _cleanup();
    setState(() {
      _isConnected = false;
      _participants = [];
      _isSafetyActive = false;
      _isRecording = false;
    });
  }

  Future<void> _toggleRecording() async {
    if (_isTogglingRecording) return;
    setState(() => _isTogglingRecording = true);

    final userName = _nameController.text.trim().isNotEmpty
        ? _nameController.text.trim()
        : 'Unknown';

    try {
      final endpoint = _isRecording ? 'stop' : 'start';
      final uri = _isRecording
          ? Uri.parse('$_recordingBaseUrl/stop?room=testroom')
          : Uri.parse('$_recordingBaseUrl/start?room=testroom&triggered_by=${Uri.encodeComponent(userName)}');

      final response = await http.post(uri).timeout(const Duration(seconds: 8));

      if (response.statusCode == 200) {
        setState(() => _isRecording = !_isRecording);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text(_isRecording ? '🔴 Recording started' : '⏹ Recording stopped & saved'),
            backgroundColor: _isRecording ? Colors.red.shade700 : Colors.green.shade700,
            duration: const Duration(seconds: 2),
          ));
        }
      } else {
        throw Exception('Status ${response.statusCode}: ${response.body}');
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('Recording error: $e'),
          backgroundColor: Colors.orange.shade700,
        ));
      }
    } finally {
      setState(() => _isTogglingRecording = false);
    }
  }

  void _updateParticipants() {
    if (_room == null) return;
    final pList = <Participant>[];
    if (_room!.localParticipant != null) pList.add(_room!.localParticipant!);
    pList.addAll(_room!.remoteParticipants.values);
    setState(() => _participants = pList);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF0F172A), Color(0xFF1E293B)],
          ),
        ),
        child: SafeArea(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildHeader(),
              const SizedBox(height: 20),
              _buildSafetyIndicator(),
              const SizedBox(height: 20),
              Expanded(child: _buildParticipantList()),
              _buildBottomAction(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Safe Environment',
            style: GoogleFonts.outfit(
              fontSize: 32,
              fontWeight: FontWeight.bold,
              color: Colors.white,
            ),
          ),
          Text(
            'Streaming raw audio for ML analysis',
            style: GoogleFonts.outfit(
              fontSize: 16,
              color: Colors.white70,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSafetyIndicator() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.05),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: Colors.white.withOpacity(0.1)),
        ),
        child: Row(
          children: [
            ScaleTransition(
              scale: _pulseController.drive(Tween(begin: 1.0, end: 1.15)),
              child: Container(
                width: 12,
                height: 12,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: _isRecording
                      ? Colors.red
                      : (_isSafetyActive ? const Color(0xFF10B981) : Colors.grey),
                  boxShadow: _isRecording
                      ? [BoxShadow(color: Colors.red.withOpacity(0.6), blurRadius: 12, spreadRadius: 3)]
                      : (_isSafetyActive ? [BoxShadow(color: const Color(0xFF10B981).withOpacity(0.5), blurRadius: 10, spreadRadius: 2)] : []),
                ),
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _isRecording
                        ? '🔴 Recording in progress'
                        : (_isSafetyActive ? 'AI Safety Monitor Active' : 'Monitor Standby'),
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                  Text(
                    _isConnected ? 'Analyzing raw audio feed...' : 'Start a call to enable ML monitoring',
                    style: const TextStyle(fontSize: 12, color: Colors.white60),
                  ),
                ],
              ),
            ),
            if (_isConnected)
              GestureDetector(
                onTap: _isTogglingRecording ? null : _toggleRecording,
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 300),
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: _isRecording ? Colors.red.withOpacity(0.2) : Colors.white.withOpacity(0.08),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(
                      color: _isRecording ? Colors.red : Colors.white24,
                    ),
                  ),
                  child: _isTogglingRecording
                      ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                      : Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(
                              _isRecording ? Icons.stop_circle : Icons.fiber_manual_record,
                              color: _isRecording ? Colors.red : Colors.white54,
                              size: 14,
                            ),
                            const SizedBox(width: 4),
                            Text(
                              _isRecording ? 'Stop' : 'Record',
                              style: TextStyle(
                                fontSize: 12,
                                color: _isRecording ? Colors.red : Colors.white54,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildParticipantList() {
    if (!_isConnected && !_isConnecting) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 40),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.lock_person_rounded, size: 80, color: Colors.white.withOpacity(0.1)),
              const SizedBox(height: 24),
              TextField(
                controller: _nameController,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  labelText: 'Enter your name (Optional)',
                  labelStyle: TextStyle(color: Colors.white.withOpacity(0.5)),
                  prefixIcon: Icon(Icons.person, color: Colors.white.withOpacity(0.5)),
                  filled: true,
                  fillColor: Colors.white.withOpacity(0.05),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(16),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Text('Ready to start secure session', style: TextStyle(color: Colors.white.withOpacity(0.3))),
            ],
          ),
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      itemCount: _participants.length,
      itemBuilder: (context, index) {
        final p = _participants[index];
        final isMe = p is LocalParticipant;
        
        return Container(
          margin: const EdgeInsets.only(bottom: 12),
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.03),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: Colors.white.withOpacity(0.05)),
          ),
          child: Row(
            children: [
              CircleAvatar(
                backgroundColor: isMe ? const Color(0xFF3B82F6) : const Color(0xFF6366F1),
                child: Text(p.identity.substring(0, 1).toUpperCase()),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      isMe ? '${p.identity} (You)' : p.identity,
                      style: const TextStyle(fontWeight: FontWeight.bold),
                    ),
                    Text(
                      p.audioTrackPublications.isNotEmpty ? 'Streaming raw audio' : 'No audio',
                      style: TextStyle(fontSize: 12, color: Colors.white70),
                    ),
                  ],
                ),
              ),
              if (p.audioTrackPublications.isNotEmpty)
                const Icon(Icons.waves, color: Color(0xFF10B981), size: 20),
            ],
          ),
        );
      },
    );
  }

  Widget _buildBottomAction() {
    return Padding(
      padding: const EdgeInsets.all(24.0),
      child: SizedBox(
        width: double.infinity,
        height: 60,
        child: ElevatedButton(
          style: ElevatedButton.styleFrom(
            backgroundColor: _isConnected ? const Color(0xFFEF4444) : const Color(0xFF3B82F6),
            foregroundColor: Colors.white,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
            elevation: 0,
          ),
          onPressed: _isConnecting ? null : (_isConnected ? _disconnect : _connect),
          child: _isConnecting
              ? const CircularProgressIndicator(color: Colors.white)
              : Text(
                  _isConnected ? 'End Secure Call' : 'Start Safe Call',
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
        ),
      ),
    );
  }
}
