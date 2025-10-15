import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:clipnote/screens/upload_screen.dart';


void main() {
  testWidgets('Upload screen renders', (WidgetTester tester) async {
    await tester.pumpWidget(const MaterialApp(home: UploadScreen()));
    expect(find.text('Clipnote Uploads'), findsOneWidget);
    expect(find.text('Pick & Upload'), findsOneWidget);
  });
}
