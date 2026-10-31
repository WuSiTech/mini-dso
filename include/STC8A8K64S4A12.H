#ifndef __STC8F_H__
#define __STC8F_H__

/* cpv - file added */

#define bit __bit  /* cpv */
#define code __code  /* cpv */


//包含本头文件后,不用另外再包含"REG51.H"
//#include "fw_reg_stc8a8k64s4.h"
#include "fw_reg_stc8a8k64d4.h"

#include "intrins.h"

#ifndef uint8
#define uint8 unsigned char
#endif

#ifndef uint16
#define uint16 unsigned int
#endif

#ifndef uint32
#define uint32 unsigned long int
#endif

#ifndef int8
#define int8 signed char
#endif

#ifndef int16
#define int16 signed int
#endif


#endif /* __STC8F_H__ */

