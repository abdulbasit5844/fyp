# shared_preferences calls its Android code from Dart over JNI, which R8 cannot
# see, so without these rules the release build crashes on start (NoSuchMethodError).
-keep class io.flutter.plugins.sharedpreferences.** { *; }
-keep class com.github.dart_lang.jni.** { *; }
# The jni package also looks up these Kotlin classes by name (the full list of
# kotlin/* names in package:jni); R8 renames or removes them otherwise.
-keep class kotlin.coroutines.** { *; }
-keep class kotlin.Result { *; }
-keep class kotlin.Result$Failure { *; }
-keep class kotlin.Unit { *; }
