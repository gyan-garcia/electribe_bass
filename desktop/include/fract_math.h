#ifndef DESKTOP_FRACT_MATH_H
#define DESKTOP_FRACT_MATH_H
#include "fract_typedef.h"
#include <limits.h>
static inline int32_t desktop_sat32(int64_t value) {
    return value > INT32_MAX ? INT32_MAX : value < INT32_MIN ? INT32_MIN : (int32_t)value;
}
static inline int16_t desktop_sat16(int64_t value) {
    return value > INT16_MAX ? INT16_MAX : value < INT16_MIN ? INT16_MIN : (int16_t)value;
}
#define DESKTOP_FRACT(bits, type) \
static inline type add_fr1x##bits(type left, type right) { return desktop_sat##bits((int64_t)left + right); } \
static inline type sub_fr1x##bits(type left, type right) { return desktop_sat##bits((int64_t)left - right); } \
static inline type abs_fr1x##bits(type value) { return desktop_sat##bits(value < 0 ? -(int64_t)value : value); } \
static inline type shl_fr1x##bits(type value, int shift) { \
    if (shift < 0) return -shift >= bits ? (value < 0 ? -1 : 0) : value >> -shift; \
    if (shift >= bits) return 0; \
    return (type)((uint32_t)value << shift); \
} \
static inline type shr_fr1x##bits(type value, int shift) { \
    if (shift < 0) return shl_fr1x##bits(value, -shift); \
    return shift >= bits ? (value < 0 ? -1 : 0) : value >> shift; \
} \
static inline int norm_fr1x##bits(type value) { \
    uint32_t magnitude = value < 0 ? (uint32_t)~value : (uint32_t)value; \
    int count = 0; \
    if (!magnitude) return bits - 1; \
    while (magnitude < ((uint32_t)1 << (bits - 2))) { magnitude <<= 1; count++; } \
    return count; \
}
DESKTOP_FRACT(32, int32_t)
DESKTOP_FRACT(16, int16_t)
static inline int32_t mult_fr1x32x32(int32_t left, int32_t right) { return desktop_sat32(((int64_t)left * right) >> 31); }
static inline int16_t mult_fr1x16(int16_t left, int16_t right) { return desktop_sat16(((int32_t)left * right) >> 15); }
static inline int16_t multr_fr1x16(int16_t left, int16_t right) { return desktop_sat16(((int64_t)left * right + 16384) >> 15); }
static inline int16_t trunc_fr1x32(int32_t value) { return value >> 16; }
static inline int32_t negate_fr1x32(int32_t value) { return desktop_sat32(-(int64_t)value); }
static inline int32_t min_fr1x32(int32_t left, int32_t right) { return left < right ? left : right; }
static inline int32_t max_fr1x32(int32_t left, int32_t right) { return left > right ? left : right; }
#endif
