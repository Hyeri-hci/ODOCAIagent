"""
의존성 파일 패턴 정의
"""

# Lock 파일 목록 (실제 설치된 패키지의 정확한 버전을 기록)
# 이 파일들은 일반 의존성 파일보다 우선적으로 처리됩니다.
LOCK_FILES = [
    # JavaScript/Node.js
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "npm-shrinkwrap.json",

    # Python
    "Pipfile.lock",
    "poetry.lock",
    "pdm.lock",

    # Ruby
    "Gemfile.lock",

    # PHP
    "composer.lock",

    # Go
    "go.sum",
    "Gopkg.lock",
    "glide.lock",

    # Rust
    "Cargo.lock",

    # Swift/iOS
    "Package.resolved",
    "Podfile.lock",
    "Cartfile.resolved",

    # .NET/C#
    "project.lock.json",
    "paket.lock",
    "packages.lock.json",

    # C/C++
    "conan.lock",

    # Dart/Flutter
    "pubspec.lock",

    # Elixir
    "mix.lock",
    "rebar.lock",

    # Haskell
    "stack.yaml.lock",
    "cabal.project.freeze",

    # R
    "renv.lock",
    "packrat.lock",

    # Julia
    "Manifest.toml",

    # Crystal
    "shard.lock",

    # Perl
    "cpanfile.snapshot",
]

# 전체 의존성 파일 목록
DEPENDENCY_FILES = [
    # JavaScript/Node.js
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "npm-shrinkwrap.json",
    "bower.json",
    "lerna.json",
    ".npmrc",
    ".yarnrc",
    ".pnpmfile.cjs",

    # Python
    "requirements.txt",
    "requirements.in",
    "requirements-dev.txt",
    "requirements-test.txt",
    "requirements-prod.txt",
    "Pipfile",
    "Pipfile.lock",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "poetry.lock",
    "pdm.lock",
    "conda.yaml",
    "conda.yml",
    "environment.yml",
    "environment.yaml",
    "tox.ini",

    # Ruby
    "Gemfile",
    "Gemfile.lock",
    ".ruby-version",
    ".rvmrc",

    # Java/JVM
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "gradle.properties",
    "gradlew",
    "gradlew.bat",
    "ivy.xml",
    "build.xml",
    ".classpath",
    ".project",

    # .NET/C#
    "packages.config",
    "*.csproj",
    "*.fsproj",
    "*.vbproj",
    "*.sln",
    "project.json",
    "project.lock.json",
    "paket.dependencies",
    "paket.lock",
    "Directory.Build.props",
    "Directory.Build.targets",
    "global.json",
    "nuget.config",

    # PHP
    "composer.json",
    "composer.lock",
    ".php-version",

    # Go
    "go.mod",
    "go.sum",
    "Gopkg.toml",
    "Gopkg.lock",
    "glide.yaml",
    "glide.lock",
    "vendor.json",
    "vendor.conf",
    "Godeps.json",

    # Rust
    "Cargo.toml",
    "Cargo.lock",
    "rust-toolchain",
    "rust-toolchain.toml",

    # Swift/iOS
    "Package.swift",
    "Package.resolved",
    "Podfile",
    "Podfile.lock",
    "Cartfile",
    "Cartfile.resolved",
    "*.xcodeproj",
    "*.xcworkspace",

    # C/C++
    "conanfile.txt",
    "conanfile.py",
    "conan.lock",
    "CMakeLists.txt",
    "cmake.toml",
    "vcpkg.json",
    "vcpkg-configuration.json",
    "Makefile",
    "makefile",
    "GNUmakefile",
    "meson.build",
    "meson_options.txt",

    # Dart/Flutter
    "pubspec.yaml",
    "pubspec.lock",
    ".flutter-plugins",
    ".flutter-plugins-dependencies",

    # Elixir
    "mix.exs",
    "mix.lock",
    "rebar.config",
    "rebar.lock",

    # Haskell
    "stack.yaml",
    "stack.yaml.lock",
    "package.yaml",
    "*.cabal",
    "cabal.project",
    "cabal.project.freeze",

    # Scala
    "build.sbt",
    "project/build.properties",
    "project/plugins.sbt",

    # Clojure
    "project.clj",
    "deps.edn",
    "boot.properties",

    # Perl
    "cpanfile",
    "cpanfile.snapshot",
    "META.json",
    "META.yml",

    # Lua
    "rockspec",
    "*.rockspec",

    # R
    "DESCRIPTION",
    "renv.lock",
    "packrat.lock",

    # Julia
    "Project.toml",
    "Manifest.toml",

    # Kotlin
    "gradle.kts",

    # Objective-C
    "Cartfile",
    "Cartfile.private",
    "Cartfile.resolved",

    # Elm
    "elm.json",
    "elm-package.json",

    # Nim
    "*.nimble",

    # Crystal
    "shard.yml",
    "shard.lock",

    # Deno
    "deno.json",
    "deno.jsonc",
    "import_map.json",
    "deps.ts",

    # Racket
    "info.rkt",

    # OCaml
    "opam",
    "*.opam",
    "dune-project",

    # F#
    "paket.references",

    # Zig
    "build.zig",
    "build.zig.zon",
]
