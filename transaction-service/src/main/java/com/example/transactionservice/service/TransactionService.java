package com.example.transactionservice.service;

import com.example.transactionservice.dto.TransactionRequest;
import com.example.transactionservice.dto.TransactionResponse;
import com.example.transactionservice.model.Transaction;
import com.example.transactionservice.model.TransactionStatus;
import com.example.transactionservice.repository.TransactionRepository;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.UUID;

@Service
public class TransactionService {

    @Autowired
    private TransactionRepository transactionRepository;

    @Autowired
    private KafkaTemplate<String, Object> kafkaTemplate;

    @Value("${app.kafka.topic.transactions}")
    private String transactionsTopic;

    public TransactionResponse createTransaction(String idempotencyKey, TransactionRequest request) {
        // Check if transaction with this idempotency key already exists
        return transactionRepository.findByIdempotencyKey(idempotencyKey)
                .map(this::entityToResponse)
                .orElseGet(() -> {
                    // Create new transaction
                    Transaction transaction = new Transaction();
                    transaction.setTransactionId(UUID.randomUUID().toString());
                    transaction.setIdempotencyKey(idempotencyKey);
                    transaction.setCustomerId(request.getCustomerId());
                    transaction.setCardId(request.getCardId());
                    transaction.setAmount(request.getAmount());
                    transaction.setCurrency(request.getCurrency());
                    transaction.setMerchant(request.getMerchant());
                    transaction.setMerchantCategory(request.getMerchantCategory());
                    transaction.setLocation(request.getLocation());
                    transaction.setLatitude(request.getLatitude());
                    transaction.setLongitude(request.getLongitude());
                    transaction.setTimestamp(request.getTimestamp());
                    transaction.setStatus(TransactionStatus.PENDING);
                    transaction.setCreatedAt(Instant.now());
                    transaction.setUpdatedAt(Instant.now());

                    // Save to database
                    Transaction saved = transactionRepository.save(transaction);

                    // Publish to Kafka
                    kafkaTemplate.send(new ProducerRecord<>(transactionsTopic, saved.getTransactionId(), saved));

                    // Return response
                    return entityToResponse(saved);
                });
    }

    private TransactionResponse entityToResponse(Transaction transaction) {
        TransactionResponse response = new TransactionResponse();
        response.setId(transaction.getId());
        response.setTransactionId(transaction.getTransactionId());
        response.setIdempotencyKey(transaction.getIdempotencyKey());
        response.setCustomerId(transaction.getCustomerId());
        response.setCardId(transaction.getCardId());
        response.setAmount(transaction.getAmount());
        response.setCurrency(transaction.getCurrency());
        response.setMerchant(transaction.getMerchant());
        response.setMerchantCategory(transaction.getMerchantCategory());
        response.setLocation(transaction.getLocation());
        response.setLatitude(transaction.getLatitude());
        response.setLongitude(transaction.getLongitude());
        response.setTimestamp(transaction.getTimestamp());
        response.setStatus(transaction.getStatus());
        response.setCreatedAt(transaction.getCreatedAt());
        response.setUpdatedAt(transaction.getUpdatedAt());
        return response;
    }
}