#ifndef BG_CHARACTER_H
#define BG_CHARACTER_H
enum { BG_CHARACTER_COUNT = 5, BG_PROFILE_JORGE = 4 };
static inline const char *bg_character_name(unsigned profile) {
    static const char *const names[BG_CHARACTER_COUNT] = {"Player 1", "Player 2", "Player 3", "Player 4", "Jorge"};
    return names[profile < BG_CHARACTER_COUNT ? profile : 0];
}
#endif
