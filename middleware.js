// middleware.js
import { NextResponse } from 'next/server';

export function middleware(request) {
    const url = request.nextUrl;
    const pathname = url.pathname;

    // 只限制 /maps/ 下的资源
    if (pathname.startsWith('/maps/')) {
        const referer = request.headers.get('referer') || '';
        const allowedHosts = ['mappoolgenerator.shop', 'map-pool-generator.vercel.app'];

        const isValid = allowedHosts.some((host) => referer.includes(host));

        if (!isValid) {
            return new Response('Forbidden', { status: 403 });
        }
    }

    return NextResponse.next();
}