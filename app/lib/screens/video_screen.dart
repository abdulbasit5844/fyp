import 'package:flutter/material.dart';
import 'package:media_kit/media_kit.dart';
import 'package:media_kit_video/media_kit_video.dart';
import 'package:provider/provider.dart';

import '../api/api_client.dart';

/// Streams an event clip from the vehicle unit (FR7.2). The stream endpoint
/// needs the bearer token, which media_kit sends as an HTTP header (SEC-4).
class VideoScreen extends StatefulWidget {
  const VideoScreen({super.key, required this.clipId, required this.title});
  final String clipId;
  final String title;

  @override
  State<VideoScreen> createState() => _VideoScreenState();
}

class _VideoScreenState extends State<VideoScreen> {
  late final Player _player = Player();
  late final VideoController _controller = VideoController(_player);
  String? _error;

  @override
  void initState() {
    super.initState();
    _open();
    _player.stream.error.listen((e) {
      if (mounted) setState(() => _error = e);
    });
  }

  Future<void> _open() async {
    final api = context.read<ApiClient>();
    await api.refresh(); // make sure the header carries a valid token
    await _player.open(Media(
      api.uri('/clips/${widget.clipId}/stream').toString(),
      httpHeaders: api.authHeaders,
    ));
  }

  @override
  void dispose() {
    _player.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.title)),
      backgroundColor: Colors.black,
      body: _error != null
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Text('Could not play the clip: $_error\nVideo playback needs Wi-Fi access to the vehicle unit.',
                    textAlign: TextAlign.center, style: const TextStyle(color: Colors.white)),
              ),
            )
          : Center(child: AspectRatio(aspectRatio: 4 / 3, child: Video(controller: _controller))),
    );
  }
}
