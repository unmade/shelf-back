type User {
    required property username -> str {
        delegated constraint exclusive;
    };
    required property password -> str;
}

type Namespace {
    required property path -> str {
        delegated constraint exclusive;
    };
    required link owner -> User;
}

type File {
    required property name -> str;
    required property path -> str {
        delegated constraint exclusive;
    };
    required property size -> int64;
    required property mtime -> float64;
    required property is_dir -> bool;

    required link namespace -> Namespace;
    link parent -> File;
}
