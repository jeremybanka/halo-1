#ifndef BG_CHARACTER_H
#define BG_CHARACTER_H
/* A profile owns identity, palette and controls. Armor is an independent,
 * repeatable match choice; adding a suit never adds another profile. */
enum { BG_PROFILE_COUNT = 4, BG_PROFILE_GREEN = 3 };
typedef enum { BG_ARMOR_SPARTAN, BG_ARMOR_JORGE, BG_ARMOR_ODST, BG_ARMOR_COUNT } bg_armor;
enum { BG_ARMOR_INFINITE_ROCKETS = 1, BG_ARMOR_BLAST_HEALTH_IMMUNE = 2, BG_ARMOR_VISR = 4 };
typedef struct {
    const char *name, *designation, *description;
    float health, shield;
    unsigned abilities, memory_bytes;
} bg_armor_definition;
static inline const bg_armor_definition *bg_armor_def(unsigned armor) {
    static const bg_armor_definition suits[BG_ARMOR_COUNT] = {
        {"Spartan", "MJOLNIR Mk V", "Standard shields\nStandard ammunition", 100, 100, 0, 4*1024*1024},
        {"Jorge", "MJOLNIR Mk IV [G-052]", "Double shields\nInfinite rockets\nBlast-proof health", 100, 200,
         BG_ARMOR_INFINITE_ROCKETS | BG_ARMOR_BLAST_HEALTH_IMMUNE, 8*1024*1024},
        {"ODST", "Halo 3: ODST", "No shields\nVISR enemy silhouettes", 100, 0,
         BG_ARMOR_VISR, 8*1024*1024}
    };
    return &suits[armor < BG_ARMOR_COUNT ? armor : BG_ARMOR_SPARTAN];
}
static inline const char *bg_profile_name(unsigned profile) {
    static const char *const names[BG_PROFILE_COUNT] = {"Player 1", "Player 2", "Player 3", "Player 4"};
    return names[profile < BG_PROFILE_COUNT ? profile : 0];
}
#endif
