#include "runtime.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>

static void random_sequences(void) {
    /* Golden Xbox-width LCG states (seed=1), not a copy of the tested loop. */
    static const uint32_t expected[] = {
        1015568748u, 1586005467u, 2165703038u, 3027450565u, 217083232u,
        1587069247u, 3327581586u, 2388811721u
    };
    uint32_t seed=1;
    for (unsigned i=0; i<sizeof(expected)/sizeof(expected[0]); i++) {
        uint16_t value=blam_seed_random(&seed);
        assert(seed==expected[i]);
        assert(value==(uint16_t)(expected[i]>>16));
    }
    seed=1;
    assert(fabsf(blam_real_seed_random(&seed)-15496.f/65535.f)<1e-7f);
    for (unsigned i=0; i<10000; i++) {
        int16_t value=blam_seed_random_range(&seed,-4,8);
        assert(value>=-4 && value<8);
        float real=blam_real_seed_random_range(&seed,-.03f,.03f);
        assert(real>=-.03f && real<=.03f);
    }
}

static void clock_scheduling(void) {
    blam_clock clock;
    blam_clock_reset(&clock);
    /* Decouple render rate from the original30Hz game clock. */
    for (unsigned i=0; i<600; i++) blam_clock_update(&clock,1.f/60.f);
    assert(clock.ticks==300);
    assert(clock.elapsed==1);
    blam_clock_reset(&clock);
    assert(blam_clock_update(&clock,1.f/120.f)==0);
    assert(fabsf(blam_clock_fraction(&clock)-.25f)<1e-5f);
    clock.paused=true;
    assert(blam_clock_update(&clock,2.f)==0);
    assert(clock.ticks==0 && clock.elapsed==0);
    clock.paused=false;
    assert(blam_clock_update(&clock,1.f)==7); /* Blam local catch-up limit. */
    assert(clock.leftover_dt==0.f);
    assert(blam_clock_update(&clock,0.f)==0); /* Discarded backlog stays gone. */
    assert(blam_clock_update(&clock,-1.f)==0);
    assert(blam_clock_update(&clock,NAN)==0);
    assert(blam_clock_update(&clock,INFINITY)==0);
    clock.speed=.5f;
    assert(blam_clock_update(&clock,1.f/15.f)==1);
}

static void expect_quaternion(const float q[4],const float expected[4]) {
    float magnitude=0;
    for (unsigned i=0;i<4;i++) {
        assert(fabsf(q[i]-expected[i])<1e-6f);
        magnitude+=q[i]*q[i];
    }
    assert(fabsf(magnitude-1.f)<1e-6f);
}

static void quaternion_interpolation(void) {
    const float identity[4]={0,0,0,1};
    const float quarter_turn[4]={0,.7071067812f,0,.7071067812f};
    const float eighth_turn[4]={0,.3826834324f,0,.9238795325f};
    float q[4];
    blam_quaternions_interpolate_and_normalize(identity,quarter_turn,0.f,q);
    expect_quaternion(q,identity);
    blam_quaternions_interpolate_and_normalize(identity,quarter_turn,1.f,q);
    expect_quaternion(q,quarter_turn);
    blam_quaternions_interpolate_and_normalize(identity,quarter_turn,.5f,q);
    expect_quaternion(q,eighth_turn);
    /* Antipodal quaternions describe the same rotation, not a path through
     * a zero quaternion. Also exercise both supported in-place aliases. */
    float positive[4]={0,.6f,0,.8f},negative[4]={0,-.6f,0,-.8f};
    const float same_rotation[4]={0,.6f,0,.8f};
    blam_quaternions_interpolate_and_normalize(positive,negative,.5f,positive);
    expect_quaternion(positive,same_rotation);
    blam_quaternions_interpolate_and_normalize(positive,negative,.75f,negative);
    expect_quaternion(negative,same_rotation);
    /* +170 to -170 degrees takes the short path through180, not zero. */
    const float left[4]={0,.9961946981f,0,.0871557427f};
    const float right[4]={0,-.9961946981f,0,.0871557427f};
    const float half_turn[4]={0,1,0,0};
    blam_quaternions_interpolate_and_normalize(left,right,.5f,q);
    expect_quaternion(q,half_turn);
    const float zero[4]={0,0,0,0},scaled_identity[4]={0,0,0,2};
    blam_quaternions_interpolate_and_normalize(zero,zero,.5f,q);
    expect_quaternion(q,identity);
    blam_quaternions_interpolate_and_normalize(scaled_identity,scaled_identity,.3f,q);
    expect_quaternion(q,identity);
}

int main(void) {
    random_sequences();clock_scheduling();quaternion_interpolation();
    puts("Blam runtime: random sequence, 30Hz clock and quaternion tests pass");
    return 0;
}
