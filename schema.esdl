type File {
    required property name -> str;
    required property path -> str;
    required property size -> int64;
    required property mtime -> float64;
    required property is_dir -> bool;

    required link mediatype -> MediaType;
    required link namespace -> Namespace;
    single link parent -> File {
        on target delete DELETE SOURCE;
    };

    constraint exclusive on ((.path, .namespace));
}

type MediaType {
    required property name -> str {
        constraint exclusive;
    };
}

type Namespace {
    required property path -> str {
        constraint exclusive;
    };
    required link owner -> User {
        on target delete DELETE SOURCE;
    };
}

type User {
    required property username -> str {
        constraint exclusive;
    };
    required property password -> str;
}
