module default {
    type Account {
        property email -> str {
            constraint exclusive;
        };
        required property first_name -> str;
        required property last_name -> str;

        required single link user -> User {
            on target delete DELETE SOURCE;
        };
    }

    type File {
        required property name -> str;
        required property path -> str;
        required property size -> int64;
        required property mtime -> float64;

        required link mediatype -> MediaType;
        required link namespace -> Namespace;

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
        required property superuser -> bool;

        multi link bookmarks -> File {
            on target delete ALLOW;
        };
    }
}
