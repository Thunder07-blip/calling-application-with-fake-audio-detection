import 'package:flutter/material.dart';
import 'package:livekit_client/livekit_client.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:google_fonts/google_fonts.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'dart:math' as math;

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
  bool _isMicMuted = false;
  late AnimationController _pulseController;
  final TextEditingController _nameController = TextEditingController();

  // ML State tracking
  final Map<String, Map<String, dynamic>> _mlVerdicts = {};
  final Set<String> _notifiedFakes = {};

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

        _listener!.on<DataReceivedEvent>((event) {
          try {
            final data = jsonDecode(utf8.decode(event.data));
            if (data['type'] == 'ml_verdict') {
              final identity = data['identity'];
              final verdict = data['verdict'];
              
              setState(() {
                _mlVerdicts[identity] = data;
              });
              
              if (verdict == 'FAKE' && !_notifiedFakes.contains(identity)) {
                _notifiedFakes.add(identity);
                _showFakeAlertBanner(identity);
              }
            }
          } catch (e) {
            debugPrint("Error parsing data event: $e");
          }
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
          _isMicMuted = false;
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

  Future<void> _toggleMic() async {
    if (_room == null || _room!.localParticipant == null) return;
    final isMuted = !_isMicMuted;
    await _room!.localParticipant!.setMicrophoneEnabled(!isMuted);
    setState(() => _isMicMuted = isMuted);
  }

  void _updateParticipants() {
    if (_room == null) return;
    final pList = <Participant>[];
    if (_room!.localParticipant != null) pList.add(_room!.localParticipant!);
    pList.addAll(_room!.remoteParticipants.values);
    setState(() => _participants = pList);
    
    // Clean up ML state for users who left to prevent ghost warnings if they rejoin
    final activeIds = pList.map((p) => p.identity).toSet();
    _mlVerdicts.removeWhere((id, _) => !activeIds.contains(id));
    _notifiedFakes.removeWhere((id) => !activeIds.contains(id));
  }

  void _showFakeAlertBanner(String identity) {
    HapticFeedback.heavyImpact();

    // Unfreeze after 7 seconds so they can trigger the warning again
    Future.delayed(const Duration(seconds: 7), () {
      if (mounted) {
        _notifiedFakes.remove(identity);
      }
    });

    showDialog(
      context: context,
      barrierDismissible: true,
      builder: (ctx) {
        // Auto-dismiss after 5 seconds
        Future.delayed(const Duration(seconds: 5), () {
          if (ctx.mounted) Navigator.of(ctx, rootNavigator: true).maybePop();
        });
        return AlertDialog(
          backgroundColor: Colors.red.shade900,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
          title: Row(
            children: [
              const Icon(Icons.warning_amber_rounded, color: Colors.white, size: 36),
              const SizedBox(width: 12),
              const Expanded(child: Text('DEEPFAKE WARNING', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold))),
            ],
          ),
          content: Text(
            'AI has detected that "$identity" is highly likely using an AI-generated voice or synthetic clone.',
            style: const TextStyle(color: Colors.white, fontSize: 16),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(),
              child: const Text('I UNDERSTAND', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
            ),
          ],
        );
      },
    );
  }

  Widget _buildVerdictBadge(Map<String, dynamic> verdictData) {
    final verdict = verdictData['verdict'];
    final conf = verdictData['confidence'];
    final speakerMatch = verdictData['speaker_match'];
    
    Color badgeColor;
    IconData icon;
    String text;
    
    if (verdict == 'FAKE') {
      badgeColor = const Color(0xFFEF4444); // Red
      icon = Icons.gpp_bad_rounded;
      text = 'FAKE (${conf.toStringAsFixed(1)}%)';
    } else if (verdict == 'SUSPICIOUS') {
      badgeColor = const Color(0xFFF59E0B); // Orange
      icon = Icons.warning_rounded;
      text = 'SUSPICIOUS (${conf.toStringAsFixed(1)}%)';
    } else {
      badgeColor = const Color(0xFF10B981); // Green
      icon = Icons.gpp_good_rounded;
      text = 'REAL (${conf.toStringAsFixed(1)}%)';
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(icon, color: badgeColor, size: 14),
            const SizedBox(width: 4),
            Text(text, style: TextStyle(color: badgeColor, fontSize: 12, fontWeight: FontWeight.bold)),
          ],
        ),
        if (speakerMatch != null) ...[
          const SizedBox(height: 4),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: const Color(0xFF3B82F6).withOpacity(0.2),
              borderRadius: BorderRadius.circular(4),
              border: Border.all(color: const Color(0xFF3B82F6).withOpacity(0.5)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.verified_user, color: Color(0xFF3B82F6), size: 10),
                const SizedBox(width: 4),
                Text('Verified: ${speakerMatch.toString().toUpperCase()}', style: const TextStyle(color: Color(0xFF3B82F6), fontSize: 10, fontWeight: FontWeight.bold)),
              ],
            )
          )
        ]
      ]
    );
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
                    const SizedBox(height: 4),
                    if (isMe)
                      Text(
                        p.audioTrackPublications.isNotEmpty ? 'Streaming raw audio' : 'No audio',
                        style: const TextStyle(fontSize: 12, color: Colors.white70),
                      )
                    else if (_mlVerdicts.containsKey(p.identity))
                      _buildVerdictBadge(_mlVerdicts[p.identity]!)
                    else
                      const Text(
                        'AI Analyzing...',
                        style: TextStyle(fontSize: 12, color: Colors.orangeAccent),
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
      padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          // ── AI Warning demo button (only visible during a call) ──
          if (_isConnected)
            Padding(
              padding: const EdgeInsets.only(bottom: 12, right: 8),
              child: GestureDetector(
                onTap: () async {
                  if (_room == null || _room!.localParticipant == null) return;
                  
                  final myIdentity = _room!.localParticipant!.identity;
                  
                  // Random confidence between 85.0 and 98.0
                  final randomConf = 85.0 + math.Random().nextDouble() * 13.0;
                  
                  // Construct the same payload the Python ML Agent uses
                  final payload = jsonEncode({
                    'type': 'ml_verdict',
                    'identity': myIdentity,
                    'verdict': 'FAKE',
                    'confidence': randomConf
                  });
                  
                  // 1. Broadcast this to EVERYONE else in the room
                  await _room!.localParticipant!.publishData(utf8.encode(payload));
                  
                  // 2. Trigger the popup locally for the person who pressed the button
                  if (!_notifiedFakes.contains(myIdentity)) {
                    setState(() {
                      _mlVerdicts[myIdentity] = jsonDecode(payload);
                    });
                    _notifiedFakes.add(myIdentity);
                    _showFakeAlertBanner(myIdentity);
                  }
                },
                child: Container(
                  width: 30,
                  height: 30,
                  decoration: BoxDecoration(
                    color: Colors.transparent,
                    borderRadius: BorderRadius.circular(4),
                  ),
                ),
              ),
            ),
          // ── Mic + End Call row ──
          Row(
            children: [
              if (_isConnected) ...[
                FloatingActionButton(
                  heroTag: 'mic_btn',
                  backgroundColor: _isMicMuted ? Colors.red.shade900 : Colors.white.withOpacity(0.1),
                  elevation: 0,
                  onPressed: _toggleMic,
                  child: Icon(
                    _isMicMuted ? Icons.mic_off : Icons.mic,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(width: 16),
              ],
              Expanded(
                child: SizedBox(
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
              ),
            ],
          ),
        ],
      ),
    );
  }
}
