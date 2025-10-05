FROM nginx:1.25-alpine

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/

# Create directories for static and media files
RUN mkdir -p /app/staticfiles /app/media

# Set proper permissions
RUN chown -R nginx:nginx /app

EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]